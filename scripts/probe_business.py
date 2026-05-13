"""Probe 主营业务构成 / 业务明细的候选接口。

iFind 的"业务明细"含销量/产量分品类，akshare 不一定能拿到这么细。
重点确认：分产品/地区的营收构成 + 单位 + 报告期。
"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import akshare as ak
import pandas as pd

pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 240)

CODE = "600362"  # 江西铜业，跟用户截图一致


def probe(name, fn):
    print(f"\n========== {name} ==========")
    t0 = time.time()
    try:
        r = fn()
        dt = time.time() - t0
        if isinstance(r, pd.DataFrame):
            print(f"shape={r.shape}  耗时={dt:.1f}s")
            print(f"columns={list(r.columns)}")
            print(r.head(15))
        else:
            print(type(r).__name__, str(r)[:600], f"耗时={dt:.1f}s")
    except Exception as e:
        print(f"ERROR ({time.time()-t0:.1f}s): {type(e).__name__}: {str(e)[:200]}")


# 同花顺主营介绍（文字，已 probe 过能通）
probe("stock_zyjs_ths", lambda: ak.stock_zyjs_ths(symbol=CODE))

# 同花顺主营构成 - 按产品/地区
probe("stock_business_composition_ths",
      lambda: ak.stock_business_composition_ths(symbol=CODE) if hasattr(ak, "stock_business_composition_ths") else "no attr")

# 东方财富主营构成
probe("stock_zygc_em",
      lambda: ak.stock_zygc_em(symbol=f"SH{CODE}") if hasattr(ak, "stock_zygc_em") else "no attr")

# 主营业务
probe("stock_main_business_em",
      lambda: ak.stock_main_business_em(symbol=CODE) if hasattr(ak, "stock_main_business_em") else "no attr")

# 新浪同业排名 - 可能含产品信息
probe("stock_zygc_ths",
      lambda: ak.stock_zygc_ths(symbol=CODE) if hasattr(ak, "stock_zygc_ths") else "no attr")
