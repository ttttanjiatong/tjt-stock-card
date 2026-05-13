"""冒烟测试 AI Executor：context 组装 + 模型调用 + JSON 解析。"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from modules.data_loader import resolve_stock, lookup_industry
from modules.red_flags import detect_red_flags
from modules.ai_views import _build_context, generate_views, _json_default

CODE = sys.argv[1] if len(sys.argv) > 1 else "002594"  # 默认比亚迪（3 条 red flag 触发）

stock = resolve_stock(CODE)
ind = lookup_industry(CODE)
if ind:
    stock.industry = ind["industry_name"]
print(f"\n=== {stock.name} ({stock.code}) | {stock.industry} ===\n")

flags = detect_red_flags(stock)
ctx = _build_context(stock, flags)
print("--- Executor 收到的 context（截短）---")
print(json.dumps(ctx, ensure_ascii=False, indent=2, default=_json_default)[:3000])

print(f"\n--- 调用模型: {os.environ.get('ANTHROPIC_MODEL')} ---")
print(f"--- base_url: {os.environ.get('ANTHROPIC_BASE_URL')} ---")
t0 = time.time()
try:
    result = generate_views(stock, flags)
    print(f"\n--- 模型返回 JSON（耗时 {time.time()-t0:.1f}s）---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
