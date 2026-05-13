"""模块三：同业对比（行业分位数）。

数据策略：取该股所属申万一级行业权重 top 25 只票（含自身）作为同业代表，
4 项核心指标分位 + 行业整体 PE 对比。
"""
from __future__ import annotations

import streamlit as st

from modules.data_loader import (
    Stock, compute_quantile, get_industry_pe, get_peer_metrics,
    get_valuation_snapshot,
)


def _fmt_pct(v):
    return f"{v:.0f}%" if v is not None else "—"


def _quantile_color(q):
    """分位 → 颜色提示：>70 高、<30 低。"""
    if q is None:
        return "off"
    if q >= 70:
        return "inverse"  # 高位
    if q <= 30:
        return "normal"
    return "off"


def render_peers(stock: Stock) -> None:
    st.subheader("③ 同业对比（行业分位）")

    if not stock.industry:
        st.warning("行业匹配失败，无法计算同业分位")
        return

    with st.spinner(f"拉取 {stock.industry} 行业同业指标..."):
        peers = get_peer_metrics(stock.code, top_n=25)
        val = get_valuation_snapshot(stock.code)
        industry_pe = get_industry_pe(stock.industry)

    if peers.empty:
        st.warning("同业数据获取失败")
        return

    sample_size = len(peers)
    sample_note = f"申万一级行业：**{stock.industry}** · 实际拉取同业 {sample_size} 只（目标 top 25）"
    if sample_size < 10:
        sample_note += " ⚠️ 样本不足，分位仅供参考"
    st.caption(sample_note)

    q_pe = compute_quantile(val["pe_ttm"], peers["pe_ttm"])
    q_roe = compute_quantile(val["roe_pct"], peers["roe_pct"])
    own_growth = peers.loc[stock.code, "rev_growth_pct"] if stock.code in peers.index else None
    q_growth = compute_quantile(own_growth, peers["rev_growth_pct"])
    q_gm = compute_quantile(val["gross_margin_pct"], peers["gross_margin_pct"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("PE 分位", _fmt_pct(q_pe),
                help=f"自身 PE_TTM {val['pe_ttm']:.1f} · 同业中位数 {peers['pe_ttm'].median():.1f}")
    col2.metric("ROE 分位", _fmt_pct(q_roe),
                help=f"自身 ROE {val['roe_pct']:.2f}% · 同业中位数 {peers['roe_pct'].median():.2f}%")
    col3.metric("营收增速分位", _fmt_pct(q_growth),
                help=f"自身 {own_growth:.1f}% · 同业中位数 {peers['rev_growth_pct'].median():.1f}%" if own_growth is not None else "—")
    col4.metric("毛利率分位", _fmt_pct(q_gm),
                help=f"自身 {val['gross_margin_pct']:.1f}% · 同业中位数 {peers['gross_margin_pct'].median():.1f}%")

    if industry_pe:
        st.caption(
            f"📊 申万 {stock.industry} 行业整体 PE_TTM {industry_pe['pe_ttm']:.1f} · "
            f"PB {industry_pe['pb']:.2f} · 共 {industry_pe['constituents']} 只成份股"
        )

    with st.expander("查看同业样本"):
        display = peers.copy()
        display = display.rename(columns={
            "pe_ttm": "PE_TTM", "roe_pct": "ROE%", "gross_margin_pct": "毛利率%",
            "net_margin_pct": "净利率%", "rev_growth_pct": "营收增速%",
            "market_cap": "市值",
        })
        display["市值"] = (display["市值"] / 1e8).round(0).astype("Int64").astype(str) + " 亿"
        st.dataframe(display.round(2), width="stretch")