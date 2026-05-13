"""模块二：财务趋势可视化（近5年）。"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from modules.data_loader import Stock, get_financial_history


def _bar_line_combo(df, bar_col, line_col, bar_name, line_name, title):
    """组合图：柱状=金额（亿），折线=增速%。"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    amounts = df[bar_col] / 1e8
    growth = df[bar_col].pct_change() * 100
    fig.add_trace(
        go.Bar(x=df.index.astype(str), y=amounts, name=bar_name,
               text=[f"{v:.1f}亿" for v in amounts], textposition="outside"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=df.index.astype(str), y=growth, name=f"{bar_name}同比%",
                   mode="lines+markers", line=dict(color="#FF6B6B")),
        secondary_y=True,
    )
    fig.update_layout(
        title=title, height=380, margin=dict(t=70, b=20, l=20, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_yaxes(title_text=f"{bar_name}（亿元）", secondary_y=False)
    fig.update_yaxes(title_text="同比 %", secondary_y=True)
    return fig


def _margin_lines(df, title):
    fig = go.Figure()
    for col, color in [("毛利率", "#4ECDC4"), ("销售净利率", "#FF6B6B")]:
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index.astype(str), y=df[col], name=col,
                mode="lines+markers+text",
                text=[f"{v:.1f}%" if v is not None else "" for v in df[col]],
                textposition="top center",
                line=dict(color=color, width=2.5),
            ))
    fig.update_layout(
        title=title, height=380, margin=dict(t=70, b=20, l=20, r=20),
        yaxis_title="百分比 (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def _cashflow_vs_profit(df, title):
    """关键质量信号：经营性现金流 vs 净利润。前者持续低于后者即盈利质量问题。"""
    fig = go.Figure()
    cf = df["经营现金流"] / 1e8
    np_ = df["归母净利润"] / 1e8
    fig.add_trace(go.Bar(
        x=df.index.astype(str), y=cf, name="经营现金流", marker_color="#4ECDC4",
        text=[f"{v:.1f}" for v in cf], textposition="outside",
    ))
    fig.add_trace(go.Bar(
        x=df.index.astype(str), y=np_, name="归母净利润", marker_color="#FFA62B",
        text=[f"{v:.1f}" for v in np_], textposition="outside",
    ))
    ratio = (df["经营现金流"] / df["归母净利润"]).round(2)
    fig.add_trace(go.Scatter(
        x=df.index.astype(str), y=ratio, name="现金流/净利润",
        mode="lines+markers+text",
        text=[f"{v:.2f}x" for v in ratio], textposition="top center",
        yaxis="y2", line=dict(color="#666", dash="dash"),
    ))
    fig.update_layout(
        title=title, height=400, barmode="group",
        margin=dict(t=70, b=20, l=20, r=20),
        yaxis=dict(title="金额（亿元）"),
        yaxis2=dict(title="比值", overlaying="y", side="right", range=[0, 3]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def render_trends(stock: Stock) -> None:
    st.subheader("② 财务趋势（近5年）")

    try:
        df = get_financial_history(stock.code)
    except Exception as e:
        st.error(f"数据获取失败：{e}")
        return
    if df.empty:
        st.warning("无可用财务历史数据")
        return

    tab1, tab2, tab3 = st.tabs(["营收 & 净利润", "利润率", "现金流 vs 净利润"])
    with tab1:
        col_a, col_b = st.columns(2)
        col_a.plotly_chart(_bar_line_combo(df, "营业总收入", None, "营业总收入", None, "营业总收入"),
                           width="stretch")
        col_b.plotly_chart(_bar_line_combo(df, "归母净利润", None, "归母净利润", None, "归母净利润"),
                           width="stretch")
    with tab2:
        st.plotly_chart(_margin_lines(df, "毛利率 / 净利率"), width="stretch")
    with tab3:
        st.plotly_chart(_cashflow_vs_profit(df, "经营性现金流 vs 归母净利润（比值<1 提示盈利质量需观察）"),
                        width="stretch")
        st.caption("💡 经营现金流/净利润 持续 < 1 是 R1 财务排雷规则的输入信号")
