"""股价走势图模块（在基本面快照下方展示近 1 年价格变化）。"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.data_loader import Stock, _daily_price


def _slice_recent(df: pd.DataFrame, days: int = 252) -> pd.DataFrame:
    """取最近 N 个交易日（默认 252 ≈ 一年）。"""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").tail(days).reset_index(drop=True)


def _price_summary(df: pd.DataFrame) -> dict:
    """期间高低、均价、涨跌幅。"""
    open_p = float(df["close"].iloc[0])
    close_p = float(df["close"].iloc[-1])
    return {
        "start_date": df["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "start_price": open_p,
        "end_price": close_p,
        "high": float(df["close"].max()),
        "low": float(df["close"].min()),
        "mean": float(df["close"].mean()),
        "return_pct": (close_p / open_p - 1) * 100 if open_p > 0 else 0.0,
        "max_drawdown_pct": _max_drawdown(df["close"]),
    }


def _max_drawdown(prices: pd.Series) -> float:
    """期间最大回撤（百分比，负数）。"""
    cummax = prices.cummax()
    dd = (prices - cummax) / cummax * 100
    return float(dd.min())


def _build_chart(df: pd.DataFrame, summary: dict, stock_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["close"],
        name="收盘价",
        mode="lines",
        line=dict(color="#4ECDC4", width=2),
        hovertemplate="%{x|%Y-%m-%d}<br>收盘 %{y:.2f} 元<extra></extra>",
    ))

    high_idx = df["close"].idxmax()
    low_idx = df["close"].idxmin()
    fig.add_trace(go.Scatter(
        x=[df.loc[high_idx, "date"]], y=[df.loc[high_idx, "close"]],
        mode="markers+text", name=f"区间高 {summary['high']:.2f}",
        marker=dict(color="#FF6B6B", size=10, symbol="triangle-up"),
        text=[f"高 {summary['high']:.2f}"], textposition="top center",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[df.loc[low_idx, "date"]], y=[df.loc[low_idx, "close"]],
        mode="markers+text", name=f"区间低 {summary['low']:.2f}",
        marker=dict(color="#4ECDC4", size=10, symbol="triangle-down"),
        text=[f"低 {summary['low']:.2f}"], textposition="bottom center",
        hoverinfo="skip",
    ))

    fig.add_hline(y=summary["mean"], line_dash="dash", line_color="#666",
                  annotation_text=f"区间均价 {summary['mean']:.2f}",
                  annotation_position="right")

    fig.update_layout(
        height=320,
        margin=dict(t=50, b=20, l=20, r=20),
        showlegend=False,
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="收盘价 (元)"),
        hovermode="x unified",
    )
    return fig


def render_price_chart(stock: Stock, days: int = 252) -> None:
    st.subheader("📈 近一年股价走势")

    try:
        df_full = _daily_price(stock.code)
    except Exception as e:
        st.warning(f"行情数据获取失败：{e}")
        return

    df = _slice_recent(df_full, days=days)
    if df.empty:
        st.warning("无可用日线数据")
        return

    summary = _price_summary(df)

    col1, col2, col3, col4 = st.columns(4)
    ret = summary["return_pct"]
    ret_color = "normal" if ret >= 0 else "inverse"
    col1.metric("区间涨跌幅", f"{ret:+.1f}%", delta=None)
    col2.metric("区间高", f"{summary['high']:.2f} 元")
    col3.metric("区间低", f"{summary['low']:.2f} 元")
    col4.metric("最大回撤", f"{summary['max_drawdown_pct']:.1f}%")

    st.caption(f"{summary['start_date']} → {summary['end_date']} · 收盘价 · 前复权")
    st.plotly_chart(_build_chart(df, summary, stock.name), width="stretch")
