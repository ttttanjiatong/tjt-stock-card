"""探测 akshare 接口可用性。"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import akshare as ak
import pandas as pd

CODE = "600219"

pd.set_option("display.max_columns", 6)
pd.set_option("display.width", 200)


def probe(name, fn):
    print(f"\n========== {name} ==========")
    try:
        r = fn()
        if isinstance(r, pd.DataFrame):
            print(f"shape={r.shape}")
            print(f"columns={list(r.columns)[:20]}")
            print(r.head(3))
        else:
            print(type(r).__name__, str(r)[:300])
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")


# 行情 / 价格类
probe("stock_zh_a_daily (sina, qfq)",
      lambda: ak.stock_zh_a_daily(symbol="sh600219", adjust="qfq").tail(5))
probe("stock_zh_a_hist (eastmoney)",
      lambda: ak.stock_zh_a_hist(symbol=CODE, period="daily",
                                  start_date="20260401", end_date="20260512"))

# 估值 / 个股信息类
probe("stock_individual_info_em", lambda: ak.stock_individual_info_em(symbol=CODE))
probe("stock_value_em", lambda: ak.stock_value_em(symbol=CODE))
probe("stock_a_indicator_em",
      lambda: ak.stock_a_indicator_em() if hasattr(ak, "stock_a_indicator_em") else "no attr")

# 行业映射
probe("stock_board_industry_name_em",
      lambda: ak.stock_board_industry_name_em().head(10))
probe("sw_index_third_info",
      lambda: ak.sw_index_third_info() if hasattr(ak, "sw_index_third_info") else "no attr")
probe("stock_industry_pe_ratio_cninfo",
      lambda: ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类", date="20260430")
      if hasattr(ak, "stock_industry_pe_ratio_cninfo") else "no attr")
