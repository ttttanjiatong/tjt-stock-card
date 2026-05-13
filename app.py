"""A股基本面速览卡片生成器 - Streamlit 入口。"""
from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

# 兼容两种环境：本地 .env / Streamlit Cloud st.secrets
load_dotenv()
try:
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    # 本地无 secrets.toml / Streamlit Cloud 找不到 secrets 时静默跳过
    pass

from modules.ai_views import render_ai_views
from modules.business_intro import render_business_intro
from modules.compare import render_compare_page
from modules.data_loader import get_peer_metrics, lookup_industry, resolve_stock
from modules.fundamentals import render_fundamentals
from modules.peers import render_peers
from modules.price_chart import render_price_chart
from modules.red_flags import detect_red_flags, render_red_flags
from modules.trends import render_trends

st.set_page_config(
    page_title="A股速览卡片",
    page_icon="📊",
    layout="wide",
)


def _render_single_stock_page() -> None:
    st.title("📊 A股基本面速览卡片")
    st.caption("5分钟建立公司第一印象 · 数据来源 akshare · AI观点强制绑定数据证据")

    query = st.text_input(
        "输入股票代码或公司名",
        placeholder="例如：600219 / 南山铝业",
    )

    if not query:
        st.info("请输入股票代码或公司名后回车")
        return

    stock = resolve_stock(query)
    if stock is None:
        st.error(f"未找到匹配股票：{query}")
        return

    with st.spinner("匹配申万行业..."):
        ind = lookup_industry(stock.code)
        if ind:
            stock.industry = ind["industry_name"]

    st.header(f"{stock.name} ({stock.code})")

    render_fundamentals(stock)
    st.divider()

    render_business_intro(stock)
    st.divider()

    render_price_chart(stock)
    st.divider()

    render_trends(stock)
    st.divider()

    render_peers(stock)
    st.divider()

    red_flags = detect_red_flags(stock)
    try:
        peer_n = len(get_peer_metrics(stock.code, top_n=25)) if stock.industry else 0
    except Exception:
        peer_n = 0
    render_red_flags(red_flags, peer_sample_size=peer_n)
    st.divider()

    render_ai_views(stock, red_flags)

    st.caption("⚠️ 本工具不提供任何投资建议，仅辅助投研信息整合")


def main() -> None:
    with st.sidebar:
        st.markdown("### 📊 A股速览卡片")
        mode = st.radio(
            "模式",
            options=["单股分析", "多股对比"],
            index=0,
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("💡 单股：完整的 7 模块卡片  \n💡 多股：最多 4 只票横向对比")
        st.divider()
        st.caption("🔧 持久化缓存已启用  \n清缓存：`python -m scripts.clear_cache`")

    if mode == "多股对比":
        render_compare_page()
    else:
        _render_single_stock_page()

    st.caption("⚠️ 本工具不提供任何投资建议，仅辅助投研信息整合")


if __name__ == "__main__":
    main()
