"""Probe 全量 股票→行业 映射接口。"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import akshare as ak
import pandas as pd

pd.set_option("display.max_columns", 12)
pd.set_option("display.width", 220)


def probe(name, fn):
    print(f"\n========== {name} ==========")
    t0 = time.time()
    try:
        r = fn()
        dt = time.time() - t0
        if isinstance(r, pd.DataFrame):
            print(f"shape={r.shape}  耗时={dt:.1f}s")
            print(f"columns={list(r.columns)}")
            print(r.head(5))
            # 看是否含 600219
            for col in r.columns:
                if r[col].astype(str).str.contains("600219").any():
                    print(f"  -> 列 [{col}] 含 600219:")
                    print(r[r[col].astype(str).str.contains("600219")].head(3))
                    break
        else:
            print(type(r).__name__, str(r)[:300], f"耗时={dt:.1f}s")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")


# 全量股票→行业映射候选
probe("stock_industry_category_cninfo", lambda: ak.stock_industry_category_cninfo(symbol="巨潮行业分类标准"))
probe("stock_classify_sina", lambda: ak.stock_classify_sina() if hasattr(ak, "stock_classify_sina") else "no attr")
probe("stock_board_industry_summary_ths", lambda: ak.stock_board_industry_summary_ths())
probe("sw_index_first_info", lambda: ak.sw_index_first_info())

# 给定个股查行业
probe("stock_industry_clf_hist_sw", lambda: ak.stock_industry_clf_hist_sw() if hasattr(ak, "stock_industry_clf_hist_sw") else "no attr")
