"""对比两次 eval 结果，展示 prompt 迭代效果。

用法：
    python -m evaluation.diff_results <round0.json> <round1.json>
    python -m evaluation.diff_results --latest 2   # 自动取最近两次
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def fmt(v):
    return f"{v:.1f}" if isinstance(v, (int, float)) else "—"


def diff(prev: dict, curr: dict) -> None:
    a, b = prev["aggregates"], curr["aggregates"]
    print(f"\n📊 Eval Diff Report")
    print(f"{'='*70}")
    print(f"  Previous: {prev.get('tag') or prev['timestamp']}  ({a['valid_n']}/{a['total_n']})")
    print(f"  Current:  {curr.get('tag') or curr['timestamp']}  ({b['valid_n']}/{b['total_n']})")
    print(f"  Executor: {curr.get('executor_model')}  |  Evaluator: {curr.get('evaluator_model')}")
    print(f"{'='*70}\n")

    print(f"{'指标':<22} {'前':>8} {'后':>8} {'Δ':>8}")
    print(f"{'-'*22} {'-'*8} {'-'*8} {'-'*8}")
    for k, label in [
        ("data_accuracy", "数据引用准确率"),
        ("logic_coverage", "关键逻辑覆盖率"),
        ("invalid_ratio_score", "无效观点比例分"),
    ]:
        prev_v = a.get(k)
        curr_v = b.get(k)
        delta = (curr_v - prev_v) if isinstance(prev_v, (int, float)) and isinstance(curr_v, (int, float)) else None
        arrow = "↑" if delta and delta > 0 else ("↓" if delta and delta < 0 else "·")
        print(f"{label:<20} {fmt(prev_v):>10} {fmt(curr_v):>10} {arrow}{fmt(abs(delta)) if delta else '0':>6}")

    print(f"\n--- 按样本 ---")
    prev_by = {s["stock"]["code"]: s for s in prev["samples"] if "scores" in s}
    curr_by = {s["stock"]["code"]: s for s in curr["samples"] if "scores" in s}
    common = sorted(set(prev_by) & set(curr_by))
    for code in common:
        p = prev_by[code]["scores"]
        c = curr_by[code]["scores"]
        print(f"  {code} {prev_by[code].get('industry','')}: "
              f"acc {fmt(p.get('data_accuracy'))}→{fmt(c.get('data_accuracy'))}  "
              f"cov {fmt(p.get('logic_coverage'))}→{fmt(c.get('logic_coverage'))}  "
              f"inv {fmt(p.get('invalid_ratio_score'))}→{fmt(c.get('invalid_ratio_score'))}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="两个 json 文件路径")
    parser.add_argument("--latest", type=int, help="取最近 N 次结果（>=2）")
    args = parser.parse_args()

    if args.latest:
        if args.latest < 2:
            sys.exit("--latest 至少要 2")
        files = sorted(RESULTS.glob("*.json"))[-args.latest:]
        if len(files) < 2:
            sys.exit(f"results 目录不足两个结果文件（找到 {len(files)} 个）")
        prev, curr = load(files[0]), load(files[-1])
    elif len(args.files) == 2:
        prev, curr = load(Path(args.files[0])), load(Path(args.files[1]))
    else:
        sys.exit("用 --latest 2 或显式指定两个文件")

    diff(prev, curr)


if __name__ == "__main__":
    main()
