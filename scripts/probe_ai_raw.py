"""Probe 方舟模型的原始返回结构（thinking + text + stop_reason）。"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from anthropic import Anthropic

client = Anthropic(timeout=120)
msg = client.messages.create(
    model=os.environ.get("ANTHROPIC_MODEL", "kimi-k2.6"),
    max_tokens=4096,
    system="你是一个严格的 JSON 输出助手。仅输出 JSON。",
    messages=[{"role": "user", "content": '请输出 JSON: {"hello": "world", "n": 42}'}],
)

print(f"model: {msg.model}")
print(f"stop_reason: {msg.stop_reason}")
print(f"usage: {msg.usage}")
print(f"\n--- content blocks ({len(msg.content)}) ---")
for i, b in enumerate(msg.content):
    typ = getattr(b, "type", "?")
    print(f"\n[{i}] type={typ}")
    if typ == "thinking":
        thinking = getattr(b, "thinking", "")
        print(f"  thinking len={len(thinking)}")
        print(f"  thinking head: {thinking[:300]}")
        print(f"  thinking tail: {thinking[-300:]}")
    elif typ == "text":
        text = getattr(b, "text", "")
        print(f"  text len={len(text)}")
        print(f"  text: {text}")
    else:
        print(f"  raw: {b}")
