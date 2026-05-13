"""轻量主营业务介绍模块。

数据源：同花顺 stock_zyjs_ths（文字描述层）。
说明：akshare 无法拿到 iFind 那种"分产品 × 分报告期"的销量/产量结构化数据，
本模块用文字介绍补足"这家公司是干什么的"这一基础信息。
"""
from __future__ import annotations

import streamlit as st

from modules.data_loader import Stock, get_business_intro


def _chip_row(label: str, items: list[str], color: str) -> None:
    """渲染一行 chip-style 标签。"""
    if not items:
        return
    chips = " ".join(
        f"<span style='display:inline-block;padding:3px 10px;margin:3px 4px 3px 0;"
        f"background:{color};color:#fff;border-radius:12px;font-size:0.85em;'>{it}</span>"
        for it in items
    )
    st.markdown(f"**{label}**<br>{chips}", unsafe_allow_html=True)


def render_business_intro(stock: Stock) -> None:
    intro = get_business_intro(stock.code)
    if intro is None or not intro.get("main_business"):
        return  # 没数据就静默不渲染，不打断卡片节奏

    st.subheader("🏷️ 主营业务")

    st.markdown(intro["main_business"])

    col1, col2 = st.columns(2)
    with col1:
        _chip_row("产品类型", intro.get("product_types", []), "#4ECDC4")
    with col2:
        _chip_row("产品名称", intro.get("product_names", []), "#FFA62B")

    if intro.get("scope"):
        with st.expander("📋 经营范围（公司章程口径）"):
            st.caption(intro["scope"])

    st.caption("ℹ️ 数据源：同花顺主营介绍（文字层）。分产品销量/产量等结构化数据需付费源（如 Tushare Pro / Wind / iFind），本工具未接入。")
