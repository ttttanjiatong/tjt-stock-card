"""模块一：公司基本面快照。"""
from __future__ import annotations

import streamlit as st

from modules.data_loader import Stock, get_valuation_snapshot


def _fmt_market_cap(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 1e12:
        return f"{v / 1e12:.2f} 万亿"
    if v >= 1e8:
        return f"{v / 1e8:.1f} 亿"
    return f"{v / 1e4:.0f} 万"


def _fmt(v: float | None, suffix: str = "", digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}{suffix}"


def render_fundamentals(stock: Stock) -> None:
    st.subheader("① 基本面快照")

    try:
        val = get_valuation_snapshot(stock.code)
    except Exception as e:
        st.error(f"数据获取失败：{e}")
        return

    period = val.get("report_period", "—")
    st.caption(f"价格截至 {val['as_of']} · 财务指标基于 {period}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("行业", stock.industry or "待匹配")
    col2.metric("最新股价", _fmt(val["price"], " 元"))
    col3.metric("总市值", _fmt_market_cap(val["market_cap"]))
    col4.metric("PE (TTM)", _fmt(val["pe_ttm"]))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("PB", _fmt(val["pb"]))
    col6.metric("ROE", _fmt(val["roe_pct"], "%"))
    col7.metric("毛利率", _fmt(val["gross_margin_pct"], "%"))
    col8.metric("净利率", _fmt(val["net_margin_pct"], "%"))
