"""模块五：AI 多空观点 + 数据证据表 - 项目灵魂模块。

核心设计：
1. 把结构化的财务数据、行业分位、排雷信号作为 context 喂给 Claude/Kimi
2. 强制 JSON 输出，每条观点必须绑定 data_reference 证据条目
3. 输出可审计 → 让"数据引用准确率"成为可机器校验的指标
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from anthropic import Anthropic

from modules.data_loader import (
    Stock, compute_quantile, get_financial_history, get_industry_pe,
    get_peer_metrics, get_valuation_snapshot,
)
from modules.red_flags import RedFlag

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _json_default(o):
    """让 numpy 标量/数组兼容 json.dumps。"""
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def _safe_float(v):
    try:
        return None if v is None or pd.isna(v) else float(v)
    except (TypeError, ValueError):
        return None


def _build_context(stock: Stock, red_flags: list[RedFlag]) -> dict:
    """组装喂给 Executor Agent 的结构化输入。

    含 5 大块：基本面快照 / 5 年趋势 / 同业分位 / 行业级指标 / 排雷信号。
    所有数值都已 round/精简，避免 prompt 过长。
    """
    try:
        val = get_valuation_snapshot(stock.code)
    except Exception:
        val = {}
    try:
        hist = get_financial_history(stock.code)
    except Exception:
        hist = pd.DataFrame()
    try:
        peers = get_peer_metrics(stock.code, top_n=25) if stock.industry else pd.DataFrame()
    except Exception:
        peers = pd.DataFrame()

    industry_pe = get_industry_pe(stock.industry) if stock.industry else None

    trends = {}
    if not hist.empty:
        for col in ["营业总收入", "归母净利润", "经营现金流", "毛利率", "销售净利率"]:
            if col in hist.columns:
                s = hist[col].dropna()
                series = [
                    {"year": int(y), "value": round(float(v), 2)}
                    for y, v in s.items()
                ]
                trends[col] = series

    peer_summary = {}
    self_quantiles = {}
    if not peers.empty:
        for col, label in [
            ("pe_ttm", "pe_ttm"),
            ("roe_pct", "roe"),
            ("gross_margin_pct", "gross_margin"),
            ("net_margin_pct", "net_margin"),
            ("rev_growth_pct", "rev_growth"),
            ("debt_ratio_pct", "debt_ratio"),
        ]:
            s = peers[col].dropna()
            if s.empty:
                continue
            peer_summary[label] = {
                "median": round(float(s.median()), 2),
                "p25": round(float(s.quantile(0.25)), 2),
                "p75": round(float(s.quantile(0.75)), 2),
                "sample_size": int(len(s)),
            }
        # 算自身在 peers 中的分位
        self_quantiles = {
            "pe_ttm": compute_quantile(val.get("pe_ttm"), peers["pe_ttm"]),
            "roe": compute_quantile(val.get("roe_pct"), peers["roe_pct"]),
            "gross_margin": compute_quantile(val.get("gross_margin_pct"), peers["gross_margin_pct"]),
            "net_margin": compute_quantile(val.get("net_margin_pct"), peers["net_margin_pct"]),
            "debt_ratio": compute_quantile(val.get("debt_ratio_pct"), peers["debt_ratio_pct"]),
        }
        self_quantiles = {k: round(v, 0) if v is not None else None for k, v in self_quantiles.items()}

    return {
        "stock": {
            "code": stock.code,
            "name": stock.name,
            "industry": stock.industry,
        },
        "fundamentals": {
            "price": _safe_float(val.get("price")),
            "pe_ttm": _safe_float(val.get("pe_ttm")),
            "pb": _safe_float(val.get("pb")),
            "roe_pct": _safe_float(val.get("roe_pct")),
            "gross_margin_pct": _safe_float(val.get("gross_margin_pct")),
            "net_margin_pct": _safe_float(val.get("net_margin_pct")),
            "debt_ratio_pct": _safe_float(val.get("debt_ratio_pct")),
            "market_cap_yi": round(val.get("market_cap", 0) / 1e8, 1) if val.get("market_cap") else None,
            "report_period": val.get("report_period"),
        },
        "trends_5yr": trends,
        "industry_benchmark": {
            "industry_pe_ttm": industry_pe["pe_ttm"] if industry_pe else None,
            "industry_pb": industry_pe["pb"] if industry_pe else None,
            "constituents": industry_pe["constituents"] if industry_pe else None,
            "peer_sample_quartiles": peer_summary,
            "self_quantiles_in_peers": self_quantiles,
        },
        "red_flags": [
            {
                "rule_id": f.rule_id,
                "name": f.name,
                "triggered": f.triggered,
                "severity": f.severity,
                "detail": f.detail,
                "evidence": f.evidence,
            }
            for f in red_flags
        ],
    }


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON。兼容 ```json ... ``` 包裹及前后冗余文字。"""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if fence:
        candidates.append(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        candidates.append(text[start:end + 1])
    candidates.append(text)
    last_err = None
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError as e:
            last_err = e
    raise ValueError(
        f"无法从模型输出中提取合法 JSON。原始 text（前 1500 字符）:\n{text[:1500]}\n\n"
        f"解析错误: {last_err}"
    )


def call_model(
    system_prompt: str,
    user_payload: dict,
    model: str | None = None,
    max_tokens: int = 16384,
    progress_cb=None,
) -> dict:
    """通用方舟/Anthropic 调用：streaming + thinking 禁用 + JSON 提取。

    Args:
        system_prompt: 系统提示词
        user_payload: 会被 json.dumps 后作为 user message content
        model: 显式指定模型；None 时读 ANTHROPIC_MODEL 环境变量
        max_tokens: 输出上限
        progress_cb: 可选回调 fn(kind, chunk)，kind ∈ {"thinking","text"}

    Returns:
        模型输出的 JSON dict。
    """
    client = Anthropic(timeout=600)
    text = ""
    stream_kwargs = dict(
        model=model or os.environ.get("ANTHROPIC_MODEL", "kimi-k2.6"),
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user",
                   "content": json.dumps(user_payload, ensure_ascii=False, default=_json_default)}],
    )
    if os.environ.get("AI_DISABLE_THINKING", "1") == "1":
        stream_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}

    with client.messages.stream(**stream_kwargs) as stream:
        for event in stream:
            if getattr(event, "type", "") != "content_block_delta":
                continue
            delta = getattr(event, "delta", None)
            if delta is None:
                continue
            if getattr(delta, "type", "") == "thinking_delta" and progress_cb:
                progress_cb("thinking", getattr(delta, "thinking", ""))
            elif getattr(delta, "type", "") == "text_delta":
                chunk = getattr(delta, "text", "")
                text += chunk
                if progress_cb:
                    progress_cb("text", chunk)
        final = stream.get_final_message()

    if not text.strip():
        types = [getattr(b, "type", "?") for b in final.content]
        raise RuntimeError(
            f"模型未输出 text 块（stop_reason={final.stop_reason}, blocks={types}, "
            f"output_tokens={final.usage.output_tokens}）。可能 thinking 占满 max_tokens。"
        )
    return _extract_json(text)


def generate_views(stock: Stock, red_flags: list[RedFlag], progress_cb=None) -> dict:
    """Executor Agent：基于结构化 context 生成多空观点 + 数据证据表。"""
    return call_model(
        system_prompt=_load_prompt("executor_prompt.md"),
        user_payload=_build_context(stock, red_flags),
        max_tokens=24576,  # 4 块 × ~5 条 × data_reference 整体约 5-6k 字，给足缓冲
        progress_cb=progress_cb,
    )


def render_ai_views(stock: Stock, red_flags: list[RedFlag]) -> None:
    st.subheader("⑤ AI 多空观点 + 数据证据表")
    st.caption("每条观点强制绑定一条结构化数据证据，可审计、可校验")

    if not st.button("🤖 生成多空观点", type="primary"):
        return

    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        st.error("未配置 API Key，请检查 .env 文件")
        return

    model_name = os.environ.get("ANTHROPIC_MODEL", "kimi-k2.6")
    status_box = st.status(f"{model_name} 正在分析...", expanded=False)
    text_chars = {"n": 0}

    def _progress(kind: str, chunk: str):
        if kind == "text":
            text_chars["n"] += len(chunk)
            status_box.update(label=f"{model_name} 正在生成 · {text_chars['n']} 字")

    try:
        result = generate_views(stock, red_flags, progress_cb=_progress)
        status_box.update(label="✅ 完成", state="complete", expanded=False)
    except json.JSONDecodeError as e:
        status_box.update(label="❌ JSON 解析失败", state="error")
        st.error(f"模型输出非合法 JSON：{e}")
        return
    except Exception as e:
        status_box.update(label="❌ 生成失败", state="error")
        st.error(f"生成失败：{type(e).__name__}: {e}")
        return

    col_bull, col_bear = st.columns(2)
    with col_bull:
        st.markdown("### 🟢 多头逻辑")
        for v in result.get("bull", []):
            st.markdown(f"- {v.get('point', '')}")
    with col_bear:
        st.markdown("### 🔴 空头逻辑")
        for v in result.get("bear", []):
            st.markdown(f"- {v.get('point', '')}")

    col_watch, col_risk = st.columns(2)
    with col_watch:
        st.markdown("### 👀 关键观察点")
        for v in result.get("watch", []):
            st.markdown(f"- {v.get('point', '')}")
    with col_risk:
        st.markdown("### ⚠️ 风险提示")
        for v in result.get("risk", []):
            st.markdown(f"- {v.get('point', '')}")

    st.markdown("### 📋 数据证据表")
    st.caption("⛓️ 每条观点强制绑定的结构化数据来源，方便审计与机器校验")
    rows = []
    for side_key, side_label in [("bull", "多"), ("bear", "空"), ("watch", "观察"), ("risk", "风险")]:
        for v in result.get(side_key, []):
            ref = v.get("data_reference", {}) or {}
            rows.append({
                "方向": side_label,
                "观点": v.get("point", ""),
                "指标": ref.get("indicator", ""),
                "数值": str(ref.get("value", "")),
                "时间": ref.get("period", ""),
                "来源": ref.get("source", ""),
            })
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)

    with st.expander("调试：模型原始 JSON 输出"):
        st.json(result)
