"""Benchmark disk cache hit vs miss."""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_loader import _ak_financial_abstract, _ak_daily_price, _ak_sw_first_info

print("First call (may hit disk cache from previous runs):")
for fn, args in [
    (_ak_financial_abstract, ("600219",)),
    (_ak_financial_abstract, ("600519",)),
    (_ak_financial_abstract, ("002594",)),
    (_ak_daily_price, ("sh600219",)),
    (_ak_sw_first_info, ()),
]:
    t = time.time()
    fn(*args)
    print(f"  {fn.__name__}{args}: {time.time()-t:.3f}s")
