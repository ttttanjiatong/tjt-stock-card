"""更精准 probe：单股查行业 + 申万一级行业成份股（31 个，可控）。"""
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
            print(f"shape={r.shape}  耗时={dt:.2f}s")
            print(f"columns={list(r.columns)}")
            print(r.head(8))
        else:
            print(type(r).__name__, str(r)[:400], f"耗时={dt:.2f}s")
    except Exception as e:
        print(f"ERROR ({time.time()-t0:.1f}s): {type(e).__name__}: {str(e)[:200]}")


# 1. 申万一级行业（31 个，已知秒回）
probe("sw_index_first_info", lambda: ak.sw_index_first_info())

# 2. 给定申万一级行业代码拉成份股
probe("index_component_sw(801010.SI)",
      lambda: ak.index_component_sw(symbol="801010") if hasattr(ak, "index_component_sw") else "no attr")
probe("sw_index_first_cons(801010)",
      lambda: ak.sw_index_first_cons(symbol="801010") if hasattr(ak, "sw_index_first_cons") else "no attr")

# 3. 单股查行业（巨潮）
probe("stock_industry_change_cninfo",
      lambda: ak.stock_industry_change_cninfo(symbol="600219") if hasattr(ak, "stock_industry_change_cninfo") else "no attr")

# 4. 雪球个股基本
probe("stock_individual_basic_info_xq SH600219",
      lambda: ak.stock_individual_basic_info_xq(symbol="SH600219"))

# 5. 同花顺主营业务（顺带能拿行业）
probe("stock_zyjs_ths 600219",
      lambda: ak.stock_zyjs_ths(symbol="600219") if hasattr(ak, "stock_zyjs_ths") else "no attr")
