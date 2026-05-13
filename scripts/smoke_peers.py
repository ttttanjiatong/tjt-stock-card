"""冒烟测试 peer 模块：行业索引 + 同业指标 + 分位数。"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_loader import (
    lookup_industry, get_industry_pe, get_peer_metrics,
    get_valuation_snapshot, compute_quantile,
)

CODE = sys.argv[1] if len(sys.argv) > 1 else "600219"

print(f"\n--- 1. 行业映射 ({CODE}) ---")
t0 = time.time()
info = lookup_industry(CODE)
print(f"耗时 {time.time()-t0:.1f}s")
print(info)

if info:
    print(f"\n--- 2. 行业级 PE ({info['industry_name']}) ---")
    print(get_industry_pe(info["industry_name"]))

print(f"\n--- 3. 同业指标（top 25）---")
t0 = time.time()
peers = get_peer_metrics(CODE, top_n=25)
print(f"耗时 {time.time()-t0:.1f}s  shape={peers.shape}")
print(peers)

print(f"\n--- 4. 自身在同业中的分位 ---")
val = get_valuation_snapshot(CODE)
print(f"PE_TTM 分位: {compute_quantile(val['pe_ttm'], peers['pe_ttm']):.0f}%" if not peers.empty else "N/A")
print(f"ROE 分位:    {compute_quantile(val['roe_pct'], peers['roe_pct']):.0f}%" if not peers.empty else "N/A")
print(f"毛利率 分位: {compute_quantile(val['gross_margin_pct'], peers['gross_margin_pct']):.0f}%" if not peers.empty else "N/A")
print(f"净利率 分位: {compute_quantile(val['net_margin_pct'], peers['net_margin_pct']):.0f}%" if not peers.empty else "N/A")
