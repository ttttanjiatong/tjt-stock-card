import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import akshare as ak
import pandas as pd

pd.set_option("display.max_columns", 12)
pd.set_option("display.width", 220)

CODE = "600219"

# 1. 完整指标名列表
print("\n===== stock_financial_abstract 指标名 =====")
df = ak.stock_financial_abstract(symbol=CODE)
print(df.iloc[:, :2].to_string())

# 2. 完整财务指标列名
print("\n===== stock_financial_analysis_indicator 列名 =====")
df2 = ak.stock_financial_analysis_indicator(symbol=CODE, start_year="2024")
print(list(df2.columns))
print("\n最新一行：")
print(df2.tail(1).T.to_string())

# 3. 行业映射候选
print("\n===== stock_individual_basic_info_xq (雪球) =====")
try:
    r = ak.stock_individual_basic_info_xq(symbol="SH600219")
    print(r)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")

print("\n===== stock_info_sh_name_code =====")
try:
    r = ak.stock_info_sh_name_code()
    print(r.shape, list(r.columns))
    print(r.head(3))
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {str(e)[:200]}")
