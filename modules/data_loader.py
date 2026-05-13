"""akshare 数据封装层。

约束：当前网络环境东方财富 push 系接口不可用，全部走新浪/交易所/申万/巨潮系列。
所有外部数据获取统一在此封装，方便缓存与替换。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import akshare as ak
import pandas as pd
import streamlit as st
from joblib import Memory

# 持久化磁盘缓存：跨进程、跨重启共享。
# st.cache_data 是 session-local 的，重启后会丢；joblib.Memory 落盘 .cache/ 永久（直到手动清理）。
# 业务上财务/行业等数据按报告期变化，长期缓存可接受；如需强刷用 python -m scripts.clear_cache。
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
_disk_cache = Memory(location=str(CACHE_DIR), verbose=0)


@_disk_cache.cache
def _ak_financial_abstract(code: str) -> pd.DataFrame:
    return ak.stock_financial_abstract(symbol=code)


@_disk_cache.cache
def _ak_daily_price(symbol_with_prefix: str) -> pd.DataFrame:
    return ak.stock_zh_a_daily(symbol=symbol_with_prefix, adjust="qfq")


@_disk_cache.cache
def _ak_sw_first_info() -> pd.DataFrame:
    return ak.sw_index_first_info()


@_disk_cache.cache
def _ak_index_component_sw(symbol: str) -> pd.DataFrame:
    return ak.index_component_sw(symbol=symbol)


@_disk_cache.cache
def _ak_zyjs_ths(code: str) -> pd.DataFrame:
    return ak.stock_zyjs_ths(symbol=code)


@dataclass
class Stock:
    code: str
    name: str
    industry: str | None = None


def _ak_prefix(code: str) -> str:
    """600/601/603/605/688/689/900 -> sh; 000/001/002/003/300/301/200 -> sz; 4/8 -> bj。"""
    if code[0] in ("6", "9"):
        return f"sh{code}"
    if code[0] in ("0", "3", "2"):
        return f"sz{code}"
    return f"bj{code}"


def _fetch_with_retry(fn, retries: int = 2, timeout: float = 15):
    """带超时的重试。akshare 的 requests 默认 timeout=None，在境外服务器访问国内
    域名时可能 hang 死整个会话，所以这里强制单次调用超时。"""
    last = None
    for _ in range(retries + 1):
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(fn).result(timeout=timeout)
        except FutureTimeout as e:
            last = TimeoutError(f"call timed out after {timeout}s")
        except Exception as e:
            last = e
    raise last


@st.cache_data(ttl=86400)
def _load_stock_list() -> pd.DataFrame:
    """合并沪深两市代码名称表。两边接口任一可用即可工作。"""
    frames = []
    try:
        sh = _fetch_with_retry(ak.stock_info_sh_name_code)
        frames.append(sh[["证券代码", "证券简称"]].rename(
            columns={"证券代码": "code", "证券简称": "name"}
        ))
    except Exception:
        pass
    try:
        sz = _fetch_with_retry(ak.stock_info_sz_name_code)
        frames.append(sz[["A股代码", "A股简称"]].rename(
            columns={"A股代码": "code", "A股简称": "name"}
        ))
    except Exception:
        pass
    if not frames:
        return pd.DataFrame(columns=["code", "name"])
    return pd.concat(frames, ignore_index=True).dropna()


def resolve_stock(query: str) -> Optional[Stock]:
    """支持股票代码或公司名作为输入，返回标准化的 Stock 对象。

    若代码表暂不可用，输入纯数字代码仍可工作（用代码本身作为占位名）。
    """
    query = query.strip()
    df = _load_stock_list()
    if query.isdigit():
        if not df.empty:
            row = df[df["code"] == query]
            if not row.empty:
                r = row.iloc[0]
                return Stock(code=str(r["code"]), name=str(r["name"]))
        return Stock(code=query, name=query)
    if df.empty:
        return None
    row = df[df["name"].str.contains(query, na=False)]
    if row.empty:
        return None
    r = row.iloc[0]
    return Stock(code=str(r["code"]), name=str(r["name"]))


# ---------- 内部工具 ----------

@st.cache_data(ttl=3600)
def _financial_abstract(code: str) -> pd.DataFrame:
    """新浪财务摘要：行=指标，列=报告期（YYYYMMDD 字符串）。两层缓存：disk + session。"""
    return _ak_financial_abstract(code)


@st.cache_data(ttl=3600)
def _daily_price(code: str) -> pd.DataFrame:
    """新浪日线，含收盘价与流通股本。两层缓存：disk + session。"""
    return _ak_daily_price(_ak_prefix(code))


def _metric_series(abs_df: pd.DataFrame, indicator: str) -> pd.Series:
    """从 stock_financial_abstract 取某个指标行，按报告期降序返回。"""
    row = abs_df[abs_df["指标"] == indicator]
    if row.empty:
        return pd.Series(dtype=float)
    s = row.iloc[0, 2:]
    s.index = pd.to_datetime(s.index, format="%Y%m%d", errors="coerce")
    return pd.to_numeric(s, errors="coerce").dropna().sort_index(ascending=False)


def _annual_series(abs_df: pd.DataFrame, indicator: str, years: int = 5) -> pd.Series:
    """取该指标近 N 个年报（12-31 报告期）。"""
    s = _metric_series(abs_df, indicator)
    annual = s[s.index.month == 12]
    return annual.head(years).sort_index()


def _latest_value(abs_df: pd.DataFrame, indicator: str) -> float | None:
    """最近一期的值（含季报）。"""
    s = _metric_series(abs_df, indicator)
    return float(s.iloc[0]) if not s.empty else None


def _latest_period(abs_df: pd.DataFrame, indicator: str = "营业总收入") -> str | None:
    """最近一期报告期文本，例如 '2026Q1'。"""
    s = _metric_series(abs_df, indicator)
    if s.empty:
        return None
    d = s.index[0]
    q = (d.month - 1) // 3 + 1
    return f"{d.year}Q{q}" if d.month != 12 else f"{d.year}年报"


def _ttm_value(abs_df: pd.DataFrame, indicator: str) -> float | None:
    """累计型指标的 TTM 还原：当期累计 + 上年年报 - 上年同期累计。

    适用于：基本每股收益、营业总收入、归母净利润、净利润、经营现金流量净额。
    """
    s = _metric_series(abs_df, indicator)
    if s.empty:
        return None
    cur_date = s.index[0]
    cur_val = float(s.iloc[0])
    if cur_date.month == 12:
        return cur_val
    last_ye = pd.Timestamp(year=cur_date.year - 1, month=12, day=31)
    last_same = pd.Timestamp(year=cur_date.year - 1, month=cur_date.month, day=cur_date.day)
    if last_ye not in s.index or last_same not in s.index:
        return None
    return cur_val + float(s.loc[last_ye]) - float(s.loc[last_same])


# ---------- 对外接口 ----------

@st.cache_data(ttl=86400)
def get_business_intro(code: str) -> dict | None:
    """同花顺主营业务介绍（文字层）：主营业务、产品类型、产品名称、经营范围。

    akshare 当前可用接口里唯一覆盖业务描述的源；销量/产量等结构化数据需要付费源。
    """
    try:
        df = _ak_zyjs_ths(code)
    except Exception:
        return None
    if df.empty:
        return None
    r = df.iloc[0]
    return {
        "main_business": str(r.get("主营业务", "") or "").strip(),
        "product_types": [s.strip() for s in str(r.get("产品类型", "") or "").split("、") if s.strip()],
        "product_names": [s.strip() for s in str(r.get("产品名称", "") or "").split("、") if s.strip()],
        "scope": str(r.get("经营范围", "") or "").strip(),
    }


@st.cache_data(ttl=3600)
def get_company_profile(code: str) -> dict:
    """公司基本信息：名称、最新价、流通股本、行业（暂未接入）。"""
    daily = _daily_price(code)
    last = daily.iloc[-1]
    return {
        "code": code,
        "industry": None,  # 当前网络下无稳定行业映射接口，PM 阶段补
        "latest_price": float(last["close"]),
        "outstanding_share": float(last["outstanding_share"]),
        "as_of": str(last["date"])[:10],
    }


@st.cache_data(ttl=3600)
def get_valuation_snapshot(code: str) -> dict:
    """估值快照：PE/PB 由最新价与最新一期 EPS/BPS 算出；ROE/毛利率/净利率直接读最新报告期。

    限制：第一版 PE 用最新报告期单季 EPS 推算，非严格 TTM。后续可累加近 4 个季度。
    """
    profile = get_company_profile(code)
    price = profile["latest_price"]
    abs_df = _financial_abstract(code)

    eps_ttm = _ttm_value(abs_df, "基本每股收益")
    bps = _latest_value(abs_df, "每股净资产")
    roe = _latest_value(abs_df, "净资产收益率(ROE)")
    gross_margin = _latest_value(abs_df, "毛利率")
    net_margin = _latest_value(abs_df, "销售净利率")
    debt_ratio = _latest_value(abs_df, "资产负债率")

    pe_ttm = price / eps_ttm if eps_ttm else None
    pb = price / bps if bps else None
    market_cap = price * profile["outstanding_share"]

    return {
        "price": price,
        "pe_ttm": pe_ttm,
        "pb": pb,
        "roe_pct": roe,
        "gross_margin_pct": gross_margin,
        "net_margin_pct": net_margin,
        "debt_ratio_pct": debt_ratio,
        "market_cap": market_cap,
        "report_period": _latest_period(abs_df),
        "as_of": profile["as_of"],
    }


@st.cache_data(ttl=3600)
def get_financial_history(code: str, years: int = 5) -> pd.DataFrame:
    """近 N 年（年度）财务序列：营收、净利润、毛利率、净利率、经营现金流。"""
    abs_df = _financial_abstract(code)
    out = pd.DataFrame({
        "营业总收入": _annual_series(abs_df, "营业总收入", years),
        "归母净利润": _annual_series(abs_df, "归母净利润", years),
        "净利润": _annual_series(abs_df, "净利润", years),
        "经营现金流": _annual_series(abs_df, "经营现金流量净额", years),
        "毛利率": _annual_series(abs_df, "毛利率", years),
        "销售净利率": _annual_series(abs_df, "销售净利率", years),
    })
    out.index = out.index.year
    out.index.name = "年份"
    return out


# ---------- 行业映射 + 同业 ----------

@st.cache_data(ttl=86400)
def _sw_first_info() -> pd.DataFrame:
    """申万 31 个一级行业 + 行业级 PE/PB。两层缓存：disk + session。"""
    return _ak_sw_first_info()


@st.cache_data(ttl=86400)
def _sw_industry_index() -> dict[str, dict]:
    """反向索引：股票代码 -> {industry_name, industry_code, weight}。

    首次构建 ~50s（31 个一级行业 × index_component_sw），落盘后跨进程秒回。
    """
    info = _sw_first_info()
    index: dict[str, dict] = {}
    for _, row in info.iterrows():
        code = str(row["行业代码"]).split(".")[0]
        name = str(row["行业名称"])
        try:
            cons = _ak_index_component_sw(code)
        except Exception:
            continue
        for _, c in cons.iterrows():
            stock_code = str(c["证券代码"]).zfill(6)
            index[stock_code] = {
                "industry_name": name,
                "industry_code": code,
                "weight": float(c.get("最新权重", 0) or 0),
            }
    return index


def lookup_industry(code: str) -> Optional[dict]:
    """单股查申万一级行业。先走全量索引（已缓存），命中失败再单点查 cninfo 备用。"""
    idx = _sw_industry_index()
    if code in idx:
        return idx[code]
    try:
        df = ak.stock_industry_change_cninfo(symbol=code)
        sw = df[df["分类标准"] == "申银万国行业分类标准"]
        if not sw.empty:
            r = sw.iloc[0]
            return {
                "industry_name": str(r["行业门类"]),
                "industry_code": str(r["行业编码"]),
                "weight": 0.0,
                "source": "cninfo_fallback",
            }
    except Exception:
        pass
    return None


def get_industry_pe(industry_name: str) -> Optional[dict]:
    """行业级 PE/PB（申万口径），用于行业整体估值参考。"""
    info = _sw_first_info()
    row = info[info["行业名称"] == industry_name]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "pe_ttm": float(r["TTM(滚动)市盈率"]),
        "pe_static": float(r["静态市盈率"]),
        "pb": float(r["市净率"]),
        "constituents": int(r["成份个数"]),
    }


@st.cache_data(ttl=3600)
def get_peer_metrics(code: str, top_n: int = 25) -> pd.DataFrame:
    """同行业代表性公司核心指标。

    实现：取该股所属申万一级行业权重 top_n 只票（含自身），拉每只票最新一期
    ROE / 毛利率 / 净利率 / 营收增速 / PE_TTM，返回 DataFrame。

    成本：top_n × ~1.5s（_financial_abstract 与 _daily_price 都已 cache）。
    用户首次查询某行业耗时 30~45s，后续命中缓存秒回。
    """
    info = lookup_industry(code)
    if not info:
        return pd.DataFrame()
    idx = _sw_industry_index()
    same_industry = [
        (c, meta["weight"]) for c, meta in idx.items()
        if meta["industry_name"] == info["industry_name"]
    ]
    same_industry.sort(key=lambda x: -x[1])
    peers = [c for c, _ in same_industry[:top_n]]
    if code not in peers:
        peers.append(code)

    def _one(c: str) -> dict | None:
        last_err = None
        for _ in range(2):  # 单条重试 1 次，规避并发场景下偶发掉包
            try:
                abs_df = _financial_abstract(c)
                daily = _daily_price(c)
                price = float(daily.iloc[-1]["close"])
                shares = float(daily.iloc[-1]["outstanding_share"])
                eps_ttm = _ttm_value(abs_df, "基本每股收益")
                return {
                    "code": c,
                    "pe_ttm": price / eps_ttm if eps_ttm and eps_ttm > 0 else None,
                    "roe_pct": _latest_value(abs_df, "净资产收益率(ROE)"),
                    "gross_margin_pct": _latest_value(abs_df, "毛利率"),
                    "net_margin_pct": _latest_value(abs_df, "销售净利率"),
                    "rev_growth_pct": _latest_value(abs_df, "营业总收入增长率"),
                    "debt_ratio_pct": _latest_value(abs_df, "资产负债率"),
                    "market_cap": price * shares,
                }
            except Exception as e:
                last_err = e
        return None

    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed([ex.submit(_one, c) for c in peers]):
            r = f.result()
            if r:
                rows.append(r)
    return pd.DataFrame(rows).set_index("code")


def compute_quantile(value: float | None, series: pd.Series) -> Optional[float]:
    """返回 value 在 series 中的百分位（0-100）。None 或空序列返回 None。"""
    if value is None:
        return None
    s = series.dropna()
    if s.empty:
        return None
    return float((s <= value).sum() / len(s) * 100)
