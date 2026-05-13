"""冒烟测试 5 条排雷规则在不同画像股票上的触发情况。"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_loader import resolve_stock, lookup_industry
from modules.red_flags import detect_red_flags

TICKERS = sys.argv[1:] or ["600219", "600519", "000858", "601318"]

for code in TICKERS:
    print(f"\n{'='*60}\n{code}\n{'='*60}")
    t0 = time.time()
    stock = resolve_stock(code)
    if stock is None:
        print(f"  (resolve failed)")
        continue
    ind = lookup_industry(code)
    if ind:
        stock.industry = ind["industry_name"]
    print(f"  {stock.name} | 行业: {stock.industry}")

    flags = detect_red_flags(stock)
    print(f"  耗时 {time.time()-t0:.1f}s\n")
    for f in flags:
        mark = "🚨 触发" if f.triggered else "✓ 未触发"
        print(f"  [{f.rule_id}] {mark} {f.name}")
        print(f"     {f.detail}")
