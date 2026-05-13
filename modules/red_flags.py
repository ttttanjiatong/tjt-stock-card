"""模块四：财务排雷信号 - 5 条规则引擎。

设计原则：用确定性规则识别异常点，AI 仅在已识别异常上归纳，不自由发挥。
排雷结果作为结构化输入喂给 ai_views，是产品的核心架构决策。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Literal

import pandas as pd
import streamlit as st

from modules.data_loader import (
    Stock, compute_quantile, get_financial_history, get_peer_metrics,
    get_valuation_snapshot,
)

Severity = Literal["high", "medium", "low"]


@dataclass
class RedFlag:
    rule_id: str
    name: str
    severity: Severity
    triggered: bool
    detail: str
    evidence: dict = field(default_factory=dict)


@dataclass
class RuleContext:
    """5 条规则共用的数据上下文，一次拉完避免每条规则重复 fetch。"""
    stock: Stock
    history: pd.DataFrame  # 近 5 年财务（含营收、归母、毛利率、净利率、经营现金流）
    valuation: dict        # PE_TTM, PB, ROE, 毛利率, 净利率, 资产负债率
    peers: pd.DataFrame    # 同业 25 只


# ---------- 5 条规则 ----------

def _rule_cashflow_vs_profit(ctx: RuleContext) -> RedFlag:
    """R1：经营现金流连续 2 年低于归母净利润 → 盈利质量异常。"""
    df = ctx.history.tail(3).dropna(subset=["经营现金流", "归母净利润"])
    if len(df) < 2:
        return RedFlag("R1_cashflow", "盈利质量异常", "high", False,
                       "数据不足", {})
    last2 = df.tail(2)
    ratios = (last2["经营现金流"] / last2["归母净利润"]).round(2)
    triggered = bool((ratios < 1).all() and (ratios > -10).all())  # 排除净利润为负的极端值
    return RedFlag(
        rule_id="R1_cashflow",
        name="盈利质量异常",
        severity="high",
        triggered=triggered,
        detail=f"近2年现金流/净利润 = {ratios.iloc[0]:.2f}x → {ratios.iloc[1]:.2f}x（持续 <1 提示利润含金量不足）"
        if triggered else f"现金流覆盖良好（{ratios.iloc[-1]:.2f}x）",
        evidence={
            "years": ratios.index.tolist(),
            "cashflow_to_profit_ratio": ratios.tolist(),
            "operating_cashflow": last2["经营现金流"].tolist(),
            "net_profit": last2["归母净利润"].tolist(),
        },
    )


def _rule_revenue_growth_slowdown(ctx: RuleContext) -> RedFlag:
    """R2：营收增速连续 2 年下降，且最新一期低于同业中位。"""
    df = ctx.history.tail(4).dropna(subset=["营业总收入"])
    if len(df) < 4:
        return RedFlag("R2_growth", "成长性放缓", "medium", False, "数据不足", {})
    growth = df["营业总收入"].pct_change().dropna() * 100  # 3 个增长率
    if len(growth) < 3:
        return RedFlag("R2_growth", "成长性放缓", "medium", False, "数据不足", {})

    declining = bool(growth.iloc[-1] < growth.iloc[-2] < growth.iloc[-3])

    peer_median = ctx.peers["rev_growth_pct"].median() if not ctx.peers.empty else None
    own_latest = float(growth.iloc[-1])
    below_peer = (peer_median is not None) and (own_latest < peer_median)

    triggered = declining and below_peer
    return RedFlag(
        rule_id="R2_growth",
        name="成长性放缓",
        severity="medium",
        triggered=triggered,
        detail=(
            f"营收增速 {growth.iloc[-3]:.1f}% → {growth.iloc[-2]:.1f}% → {growth.iloc[-1]:.1f}%，"
            f"且低于同业中位 {peer_median:.1f}%"
        ) if triggered else f"营收增速 {own_latest:.1f}%（行业中位 {peer_median:.1f}%）"
        if peer_median is not None else f"营收增速 {own_latest:.1f}%",
        evidence={
            "growth_pct_3yr": growth.tolist(),
            "years": growth.index.tolist(),
            "own_latest_growth_pct": own_latest,
            "peer_median_growth_pct": peer_median,
        },
    )


def _rule_margin_pressure(ctx: RuleContext) -> RedFlag:
    """R3：毛利率连续 2 年下滑 → 行业竞争加剧或成本上行。"""
    df = ctx.history.tail(3).dropna(subset=["毛利率"])
    if len(df) < 3:
        return RedFlag("R3_margin", "毛利率压力", "medium", False, "数据不足", {})
    m = df["毛利率"]
    triggered = bool(m.iloc[-1] < m.iloc[-2] < m.iloc[-3])
    return RedFlag(
        rule_id="R3_margin",
        name="毛利率压力",
        severity="medium",
        triggered=triggered,
        detail=(
            f"毛利率 {m.iloc[-3]:.1f}% → {m.iloc[-2]:.1f}% → {m.iloc[-1]:.1f}%（连续2年下滑）"
        ) if triggered else f"毛利率 {m.iloc[-1]:.1f}%（趋势稳定）",
        evidence={
            "gross_margin_pct_3yr": m.tolist(),
            "years": m.index.tolist(),
            "delta_2yr": float(m.iloc[-1] - m.iloc[-3]),
        },
    )


def _rule_leverage_pressure(ctx: RuleContext) -> RedFlag:
    """R4：资产负债率显著高于同业（落在同业 70 分位以上）→ 负债压力。

    简化版：不再单独拉短期借款数据。资产负债率本身已足够发出预警信号。
    样本量 <10 时不触发（分位数无统计意义）。
    """
    own = ctx.valuation.get("debt_ratio_pct")
    peer_series = ctx.peers["debt_ratio_pct"].dropna() if not ctx.peers.empty else pd.Series(dtype=float)
    if own is None or len(peer_series) < 10:
        return RedFlag("R4_leverage", "负债压力", "high", False,
                       f"同业样本不足（{len(peer_series)} 只），跳过分位判定", {})

    q = compute_quantile(own, peer_series)
    peer_median = float(peer_series.median())
    triggered = (q is not None) and (q >= 70)
    return RedFlag(
        rule_id="R4_leverage",
        name="负债压力",
        severity="high",
        triggered=triggered,
        detail=(
            f"资产负债率 {own:.1f}%（行业 {q:.0f} 分位，中位 {peer_median:.1f}%）"
        ) if triggered else f"资产负债率 {own:.1f}%（行业 {q:.0f} 分位）",
        evidence={
            "debt_ratio_pct": own,
            "peer_quantile": q,
            "peer_median_pct": peer_median,
        },
    )


def _rule_valuation_mismatch(ctx: RuleContext) -> RedFlag:
    """R5：PE/PB 位于行业 70 分位以上，但 ROE 位于行业 30 分位以下 → 估值与基本面不匹配。

    样本量 <10 时不触发（分位数无统计意义）。
    """
    pe_n = ctx.peers["pe_ttm"].dropna().shape[0] if not ctx.peers.empty else 0
    roe_n = ctx.peers["roe_pct"].dropna().shape[0] if not ctx.peers.empty else 0
    if pe_n < 10 or roe_n < 10:
        return RedFlag("R5_valuation", "估值-基本面错配", "medium", False,
                       f"同业样本不足（PE {pe_n} / ROE {roe_n}），跳过分位判定", {})

    q_pe = compute_quantile(ctx.valuation.get("pe_ttm"), ctx.peers["pe_ttm"])
    q_roe = compute_quantile(ctx.valuation.get("roe_pct"), ctx.peers["roe_pct"])

    high_val = (q_pe is not None and q_pe >= 70)
    low_quality = (q_roe is not None and q_roe <= 30)
    triggered = high_val and low_quality

    return RedFlag(
        rule_id="R5_valuation",
        name="估值-基本面错配",
        severity="medium",
        triggered=triggered,
        detail=(
            f"PE {ctx.valuation['pe_ttm']:.1f}（行业 {q_pe:.0f} 分位）+ "
            f"ROE {ctx.valuation['roe_pct']:.2f}%（{q_roe:.0f} 分位）"
        ) if triggered else (
            f"PE 分位 {q_pe:.0f} / ROE 分位 {q_roe:.0f}（无错配）"
            if q_pe is not None and q_roe is not None else "数据不足"
        ),
        evidence={
            "pe_ttm": ctx.valuation.get("pe_ttm"),
            "pe_quantile": q_pe,
            "roe_pct": ctx.valuation.get("roe_pct"),
            "roe_quantile": q_roe,
        },
    )


RULES = [
    _rule_cashflow_vs_profit,
    _rule_revenue_growth_slowdown,
    _rule_margin_pressure,
    _rule_leverage_pressure,
    _rule_valuation_mismatch,
]


# ---------- 对外 ----------

def detect_red_flags(stock: Stock) -> list[RedFlag]:
    """构建 RuleContext 然后跑 5 条规则。"""
    try:
        history = get_financial_history(stock.code)
        valuation = get_valuation_snapshot(stock.code)
    except Exception:
        return []

    peers = pd.DataFrame()
    if stock.industry:
        try:
            peers = get_peer_metrics(stock.code, top_n=25)
        except Exception:
            pass

    ctx = RuleContext(stock=stock, history=history, valuation=valuation, peers=peers)
    return [rule(ctx) for rule in RULES]


def render_red_flags(flags: list[RedFlag], peer_sample_size: int | None = None) -> None:
    st.subheader("④ 财务排雷信号")
    extra = f" · 同业样本 {peer_sample_size} 只" if peer_sample_size is not None else ""
    st.caption(f"基于 5 条投研框架规则的确定性检测，命中的异常项作为结构化输入喂给 AI 模块{extra}")

    if not flags:
        st.warning("数据获取失败，无法运行排雷规则")
        return

    triggered = [f for f in flags if f.triggered]
    if not triggered:
        st.success(f"✅ 5 条规则均未触发异常（{len(flags)} 条已检测）")
    else:
        for f in triggered:
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[f.severity]
            st.warning(f"{emoji} **{f.name}** — {f.detail}")

    with st.expander("查看所有规则状态（含未触发）"):
        for f in flags:
            status = "🚨 触发" if f.triggered else "✓ 未触发"
            st.markdown(f"**{f.rule_id} · {f.name}** — {status}")
            st.caption(f.detail)
        st.divider()
        st.markdown("**结构化 evidence（即将传入 AI 模块作为 context）：**")
        st.json([asdict(f) for f in flags])
