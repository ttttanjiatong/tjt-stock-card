"""多股对比页面 - 仪表盘式布局。

设计：
1. 顶部股票选择条（chip + 输入框，最多 3-4 只）
2. 一、关键指标对比表（热力色编码）
3. 二、5 年财务趋势叠加图
4. 三、近一年股价归一化叠加图
5. 四、排雷信号并排卡片
6. 五、AI 综合横评（一次模型调用对比 N 只票）
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.ai_views import _build_context, _json_default, call_model
from modules.data_loader import (
    Stock, _daily_price, get_financial_history, get_valuation_snapshot,
    lookup_industry, resolve_stock,
)
from modules.red_flags import detect_red_flags

MAX_STOCKS = 4

# 颜色板：每只票一个稳定的色
PALETTE = ["#4ECDC4", "#FF6B6B", "#FFA62B", "#9D6FFF"]

# 指标方向：True = 高好（绿色高），False = 低好
METRIC_DIR = {
    "PE_TTM": False,
    "PB": False,
    "ROE %": True,
    "毛利率 %": True,
    "净利率 %": True,
    "资产负债率 %": False,
    "总市值 (亿)": True,
    "近1年涨跌 %": True,
    "同业 PE 分位": False,
    "同业 ROE 分位": True,
    "排雷触发数": False,
}


# ---------- 顶部股票选择条 ----------

def _render_stock_selector() -> list[Stock]:
    """渲染顶部水平股票选择条，返回当前选中的 Stock 列表。"""
    if "compare_stocks" not in st.session_state:
        st.session_state.compare_stocks = []

    stocks: list[Stock] = st.session_state.compare_stocks

    # === Chip 行（删除按钮 + 清空按钮）===
    if stocks:
        cols = st.columns([1] * len(stocks) + [1])
        for i, s in enumerate(stocks):
            with cols[i]:
                if st.button(f"✕ {s.name}", key=f"rm_{s.code}", width="stretch"):
                    st.session_state.compare_stocks = [x for x in stocks if x.code != s.code]
                    st.rerun()
        if cols[-1].button("🗑 清空全部", width="stretch", key="clear_all"):
            st.session_state.compare_stocks = []
            st.rerun()

    # === 输入 form（clear_on_submit 自动清空输入框，规避 widget 状态修改报错）===
    can_add = len(stocks) < MAX_STOCKS
    placeholder = "输入股票代码或公司名（按回车或点添加）" if can_add else f"已达上限 {MAX_STOCKS} 只"

    with st.form("add_stock_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([5, 1])
        new_query = c1.text_input(
            "添加股票",
            placeholder=placeholder,
            label_visibility="collapsed",
            disabled=not can_add,
        )
        submitted = c2.form_submit_button("+ 添加", width="stretch", disabled=not can_add)

    if submitted and new_query and new_query.strip():
        if _try_add_stock(new_query):
            st.rerun()

    return st.session_state.compare_stocks


def _try_add_stock(query: str) -> bool:
    stock = resolve_stock(query.strip())
    if stock is None:
        st.warning(f"未找到 {query}")
        return False
    existing = {s.code for s in st.session_state.compare_stocks}
    if stock.code in existing:
        st.warning(f"{stock.name} 已在对比列表中")
        return False
    ind = lookup_industry(stock.code)
    if ind:
        stock.industry = ind["industry_name"]
    st.session_state.compare_stocks.append(stock)
    return True


# ---------- 数据加载（并发） ----------

def _load_for_one(stock: Stock) -> dict:
    val = get_valuation_snapshot(stock.code)
    hist = get_financial_history(stock.code)
    daily = _daily_price(stock.code).copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily_1y = daily.sort_values("date").tail(252).reset_index(drop=True)
    flags = detect_red_flags(stock)

    return {
        "stock": stock,
        "val": val,
        "hist": hist,
        "daily_1y": daily_1y,
        "flags": flags,
    }


def _load_all(stocks: list[Stock]) -> dict[str, dict]:
    """并发加载所有股票的数据。"""
    out = {}
    with ThreadPoolExecutor(max_workers=min(len(stocks), 4)) as ex:
        futures = {ex.submit(_load_for_one, s): s for s in stocks}
        for f in as_completed(futures):
            s = futures[f]
            try:
                out[s.code] = f.result()
            except Exception as e:
                st.error(f"{s.name} 数据加载失败：{e}")
    return out


# ---------- 一、关键指标对比表 ----------

def _build_metrics_df(stocks: list[Stock], data: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for s in stocks:
        d = data.get(s.code)
        if not d:
            continue
        val = d["val"]
        hist = d["hist"]
        daily = d["daily_1y"]
        flags = d["flags"]

        # 近1年股价涨跌
        ret_pct = None
        if len(daily) >= 2:
            ret_pct = (float(daily["close"].iloc[-1]) / float(daily["close"].iloc[0]) - 1) * 100

        # 营收增速（最近一年）
        rev = hist["营业总收入"].dropna() if not hist.empty else pd.Series(dtype=float)
        rev_growth = (rev.iloc[-1] / rev.iloc[-2] - 1) * 100 if len(rev) >= 2 else None

        rows.append({
            "stock": f"{s.name} ({s.code})",
            "industry": s.industry or "—",
            "PE_TTM": val.get("pe_ttm"),
            "PB": val.get("pb"),
            "ROE %": val.get("roe_pct"),
            "毛利率 %": val.get("gross_margin_pct"),
            "净利率 %": val.get("net_margin_pct"),
            "资产负债率 %": val.get("debt_ratio_pct"),
            "总市值 (亿)": (val.get("market_cap") or 0) / 1e8,
            "营收增速 %": rev_growth,
            "近1年涨跌 %": ret_pct,
            "排雷触发数": sum(1 for f in flags if f.triggered),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("stock").T
    return df


def _color_row(series: pd.Series, direction_high_is_good: bool) -> list[str]:
    """对一行（同指标横跨各股）做颜色映射：好=绿、差=红，渐变。"""
    nums = pd.to_numeric(series, errors="coerce")
    if nums.dropna().empty or nums.dropna().nunique() < 2:
        return ["" for _ in series]
    rank = nums.rank(pct=True, ascending=direction_high_is_good)  # 0-1
    colors = []
    for v in rank:
        if pd.isna(v):
            colors.append("")
        elif v >= 0.67:
            colors.append("background-color: rgba(78, 205, 196, 0.35); color: white")  # 深绿
        elif v >= 0.34:
            colors.append("background-color: rgba(78, 205, 196, 0.15)")  # 浅绿
        elif v >= 0.0:
            colors.append("background-color: rgba(255, 107, 107, 0.25)")  # 浅红
        else:
            colors.append("")
    return colors


def _render_metrics_table(stocks: list[Stock], data: dict[str, dict]) -> None:
    st.markdown("### 一、关键指标对比")
    st.caption("色块编码：🟢 绿色越深 = 该指标维度下越优 ｜ 🔴 红色 = 相对劣势")

    df = _build_metrics_df(stocks, data)
    if df.empty:
        st.warning("无可用数据")
        return

    # 行业 / 排雷触发数 这类不参与颜色编码或单独处理
    styled = df.copy()

    def _apply(row):
        name = row.name
        if name in METRIC_DIR:
            return _color_row(row, METRIC_DIR[name])
        return ["" for _ in row]

    styler = styled.style.apply(_apply, axis=1)

    # 格式化数字
    def _fmt(v):
        if pd.isna(v) or v is None:
            return "—"
        if isinstance(v, (int, float)):
            return f"{v:.2f}" if abs(v) < 1000 else f"{v:,.0f}"
        return str(v)

    styler = styler.format(_fmt)
    st.dataframe(styler, width="stretch", height=460)


# ---------- 二、5 年财务趋势叠加图 ----------

def _trend_overlay(stocks: list[Stock], data: dict[str, dict], col: str, title: str, unit: str) -> go.Figure:
    fig = go.Figure()
    for i, s in enumerate(stocks):
        d = data.get(s.code)
        if not d or d["hist"].empty or col not in d["hist"].columns:
            continue
        series = d["hist"][col].dropna()
        if series.empty:
            continue
        y = series / 1e8 if unit == "亿" else series
        fig.add_trace(go.Scatter(
            x=series.index.astype(str), y=y,
            name=s.name, mode="lines+markers",
            line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
            hovertemplate=f"%{{x}}<br>{s.name}: %{{y:.2f}} {unit}<extra></extra>",
        ))
    fig.update_layout(
        title=title, height=380, margin=dict(t=60, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis_title=unit,
    )
    return fig


def _render_trends_overlay(stocks: list[Stock], data: dict[str, dict]) -> None:
    st.markdown("### 二、5 年财务趋势对比")
    tab1, tab2, tab3, tab4 = st.tabs(["营业总收入", "归母净利润", "毛利率", "ROE"])
    with tab1:
        st.plotly_chart(_trend_overlay(stocks, data, "营业总收入", "营业总收入（近 5 年）", "亿"),
                        width="stretch")
    with tab2:
        st.plotly_chart(_trend_overlay(stocks, data, "归母净利润", "归母净利润（近 5 年）", "亿"),
                        width="stretch")
    with tab3:
        st.plotly_chart(_trend_overlay(stocks, data, "毛利率", "毛利率（近 5 年）", "%"),
                        width="stretch")
    with tab4:
        # ROE 不在 financial_history 里，从年度数据近似（净利/股东权益），这里跳过用简化展示
        roe_fig = go.Figure()
        for i, s in enumerate(stocks):
            d = data.get(s.code)
            if not d or d["hist"].empty:
                continue
            hist = d["hist"]
            if "归母净利润" in hist and "营业总收入" in hist:
                # 简化：用净利率代替 ROE 在多年序列里的展示
                ratio = (hist["归母净利润"] / hist["营业总收入"] * 100).dropna()
                roe_fig.add_trace(go.Scatter(
                    x=ratio.index.astype(str), y=ratio, name=s.name,
                    mode="lines+markers",
                    line=dict(color=PALETTE[i % len(PALETTE)], width=2.5),
                    hovertemplate=f"%{{x}}<br>{s.name}: %{{y:.2f}}%<extra></extra>",
                ))
        roe_fig.update_layout(
            title="销售净利率（近 5 年，简化版 ROE 代理指标）", height=380,
            margin=dict(t=60, b=20, l=20, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            yaxis_title="%",
        )
        st.plotly_chart(roe_fig, width="stretch")
        st.caption("⚠️ 本图为简化版（归母净利润/营业总收入），严格 ROE 需要逐期净资产数据")


# ---------- 三、股价归一化叠加图 ----------

def _render_price_overlay(stocks: list[Stock], data: dict[str, dict]) -> None:
    st.markdown("### 三、近 1 年股价相对走势")
    st.caption("起点归一化到 100，便于直接读相对收益")

    fig = go.Figure()
    for i, s in enumerate(stocks):
        d = data.get(s.code)
        if not d or d["daily_1y"].empty:
            continue
        df = d["daily_1y"]
        base = float(df["close"].iloc[0])
        if base <= 0:
            continue
        normalized = df["close"] / base * 100
        end_return = (normalized.iloc[-1] - 100)
        fig.add_trace(go.Scatter(
            x=df["date"], y=normalized,
            name=f"{s.name} ({end_return:+.1f}%)",
            mode="lines",
            line=dict(color=PALETTE[i % len(PALETTE)], width=2),
            hovertemplate=f"%{{x|%Y-%m-%d}}<br>{s.name}: %{{y:.2f}}<extra></extra>",
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#666",
                  annotation_text="起点 100", annotation_position="right")
    fig.update_layout(
        height=380, margin=dict(t=40, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis_title="归一化价格", xaxis_title="",
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


# ---------- 四、排雷信号对比 ----------

def _render_red_flags_compare(stocks: list[Stock], data: dict[str, dict]) -> None:
    st.markdown("### 四、财务排雷信号对比")
    cols = st.columns(len(stocks))
    for i, s in enumerate(stocks):
        with cols[i]:
            d = data.get(s.code)
            if not d:
                st.warning(f"{s.name} 数据不可用")
                continue
            flags = d["flags"]
            triggered = [f for f in flags if f.triggered]

            st.markdown(f"#### {s.name}")
            st.caption(s.industry or "—")

            if not triggered:
                st.success(f"✅ 5 条规则均未触发")
            else:
                for f in triggered:
                    emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}[f.severity]
                    st.warning(f"{emoji} **{f.name}**")
                    st.caption(f.detail)


# ---------- 五、AI 综合横评 ----------

COMPARE_PROMPT = """# 横向对比研究员

**输出协议**：直接输出 JSON，不要任何思考过程或解释文字。第一个字符 `{`，最后一个 `}`。

你是 A 股横向对比研究员，基于用户提供的 N 只股票的结构化数据，输出**对比分析**。

## 硬性约束

1. **每条对比必须明确指出谁 vs 谁**，例如"茅台 vs 五粮液：净利率 52% vs 36%，茅台高出 16pct"
2. **绝不输出投资建议**，不写"建议买茅台"
3. **每条对比必须绑定数据**，data_reference 含 stock_code/indicator/value/period
4. **不在 raw_data 之外编造数据**

## 输出格式

```json
{
  "comparison_summary": "<一段 50-100 字的总体对比综述>",
  "valuation": [{"point": "...", "data_reference": {...}}],
  "profitability": [{"point": "...", "data_reference": {...}}],
  "growth": [{"point": "...", "data_reference": {...}}],
  "risk": [{"point": "...", "data_reference": {...}}],
  "verdict": "<一段 50 字的相对画像总结，禁止投资建议>"
}
```

每个数组 2-3 条。"""


def _render_ai_compare(stocks: list[Stock], data: dict[str, dict]) -> None:
    st.markdown("### 五、AI 综合横评")
    st.caption("一次模型调用，对比 N 只票的估值/盈利/成长/风险并给出相对画像（不输出投资建议）")

    if not st.button("🤖 生成 AI 横向对比", type="primary", key="ai_compare_btn"):
        return

    payload = {
        "stocks": [{
            "code": s.code,
            "name": s.name,
            "industry": s.industry,
            "context": _build_context(s, data[s.code]["flags"]) if s.code in data else None,
        } for s in stocks if s.code in data],
    }

    status_box = st.status("AI 正在对比...", expanded=False)
    text_chars = {"n": 0}

    def _progress(kind, chunk):
        if kind == "text":
            text_chars["n"] += len(chunk)
            status_box.update(label=f"AI 生成中 · {text_chars['n']} 字")

    try:
        result = call_model(
            system_prompt=COMPARE_PROMPT,
            user_payload=payload,
            max_tokens=24576,
            progress_cb=_progress,
        )
        status_box.update(label="✅ 完成", state="complete", expanded=False)
    except Exception as e:
        status_box.update(label="❌ 失败", state="error")
        st.error(f"生成失败：{type(e).__name__}: {e}")
        return

    if result.get("comparison_summary"):
        st.info(result["comparison_summary"])

    sections = [
        ("💰 估值对比", "valuation"),
        ("📈 盈利能力对比", "profitability"),
        ("🚀 成长性对比", "growth"),
        ("⚠️ 风险对比", "risk"),
    ]
    for title, key in sections:
        items = result.get(key, [])
        if not items:
            continue
        st.markdown(f"#### {title}")
        for v in items:
            st.markdown(f"- {v.get('point', '')}")

    if result.get("verdict"):
        st.markdown("#### 🎯 相对画像")
        st.success(result["verdict"])

    rows = []
    for key in ["valuation", "profitability", "growth", "risk"]:
        for v in result.get(key, []):
            ref = v.get("data_reference", {}) or {}
            rows.append({
                "维度": key,
                "对比观点": v.get("point", ""),
                "股票": ref.get("stock_code", ""),
                "指标": ref.get("indicator", ""),
                "数值": str(ref.get("value", "")),
                "时间": ref.get("period", ""),
            })
    if rows:
        with st.expander("📋 数据证据表"):
            st.dataframe(rows, width="stretch", hide_index=True)


# ---------- 主入口 ----------

def render_compare_page() -> None:
    st.title("📊 多股对比")
    st.caption("最多 4 只股票横向对比 · 关键指标 / 财务趋势 / 股价走势 / 排雷信号 / AI 综合点评")

    st.markdown("##### 选择股票")
    stocks = _render_stock_selector()

    if not stocks:
        st.info("👆 输入股票代码或公司名，添加到对比列表（如 600519、002594、600519，600362）")
        with st.expander("💡 推荐对比组合"):
            st.markdown("""
- **白酒龙头**：600519 茅台 / 000858 五粮液 / 000568 泸州老窖
- **新能源车**：002594 比亚迪 / 300750 宁德时代
- **有色金属**：600219 南山铝业 / 600362 江西铜业
- **银行**：600036 招商银行 / 601318 中国平安
            """)
        return

    if len(stocks) < 2:
        st.info(f"已添加 1 只票，再加 1 只即可开始对比")
        return

    with st.spinner(f"加载 {len(stocks)} 只票的数据..."):
        data = _load_all(stocks)

    st.divider()
    _render_metrics_table(stocks, data)
    st.divider()
    _render_trends_overlay(stocks, data)
    st.divider()
    _render_price_overlay(stocks, data)
    st.divider()
    _render_red_flags_compare(stocks, data)
    st.divider()
    _render_ai_compare(stocks, data)
