"""冒烟测试 data_loader 真实数据。"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 关掉 streamlit 的 cache_data 装饰器在脚本环境下的警告
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

from modules.data_loader import resolve_stock, get_company_profile, get_valuation_snapshot, get_financial_history

for code in ["600219", "600519", "000858"]:
    print(f"\n========== {code} ==========")
    s = resolve_stock(code)
    print("resolve:", s)
    print("profile:", get_company_profile(code))
    val = get_valuation_snapshot(code)
    print("valuation:")
    for k, v in val.items():
        print(f"  {k}: {v}")
    print("\n5年财务历史:")
    print(get_financial_history(code).to_string())
