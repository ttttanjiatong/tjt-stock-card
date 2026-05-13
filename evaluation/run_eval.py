"""双 Agent 自动化评估 pipeline (LLM-as-a-Judge)。

异厂模型组合避免自评偏置：
    Executor  = ANTHROPIC_MODEL          （默认 kimi-k2.6 - 月之暗面）
    Evaluator = ANTHROPIC_EVALUATOR_MODEL（默认 glm-5.1   - 智谱）

用法：
    python -m evaluation.run_eval [--limit N] [--tag prompt_v1]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
load_dotenv(ROOT.parent / ".env")

from modules.ai_views import _build_context, _load_prompt, call_model  # noqa: E402
from modules.data_loader import Stock, lookup_industry  # noqa: E402
from modules.red_flags import detect_red_flags  # noqa: E402

RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)

EXECUTOR_MODEL = os.environ.get("ANTHROPIC_MODEL", "kimi-k2.6")
EVALUATOR_MODEL = os.environ.get("ANTHROPIC_EVALUATOR_MODEL") or EXECUTOR_MODEL


def run_executor(context: dict) -> dict:
    return call_model(
        system_prompt=_load_prompt("executor_prompt.md"),
        user_payload=context,
        model=EXECUTOR_MODEL,
        max_tokens=24576,
    )


def run_evaluator(raw_data: dict, executor_output: dict) -> dict:
    """评估 Executor 输出。刻意使用与 Executor 不同的模型，避免 LLM-as-a-Judge 自评偏置。"""
    return call_model(
        system_prompt=_load_prompt("evaluator_prompt.md"),
        user_payload={"raw_data": raw_data, "executor_output": executor_output},
        model=EVALUATOR_MODEL,
        max_tokens=8192,
    )


def evaluate_sample(sample: dict) -> dict:
    code = sample["code"]
    stock = Stock(code=code, name=sample["name"])
    ind = lookup_industry(code)
    if ind:
        stock.industry = ind["industry_name"]

    red_flags = detect_red_flags(stock)
    context = _build_context(stock, red_flags)

    t0 = time.time()
    executor_output = run_executor(context)
    t_exec = time.time() - t0

    t0 = time.time()
    scores = run_evaluator(context, executor_output)
    t_eval = time.time() - t0

    return {
        "stock": sample,
        "industry": stock.industry,
        "executor_output": executor_output,
        "scores": scores,
        "timing": {"executor_s": round(t_exec, 1), "evaluator_s": round(t_eval, 1)},
    }


def _mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return round(statistics.mean(nums), 1) if nums else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="限制评估前 N 只票，调试用")
    parser.add_argument("--tag", default="", help="本轮评估的 tag，便于结果对比")
    parser.add_argument("--codes", nargs="*", help="只评估指定股票代码（覆盖 sample_stocks.json）")
    args = parser.parse_args()

    if args.codes:
        samples = [{"code": c, "name": c} for c in args.codes]
    else:
        samples = json.loads((ROOT / "sample_stocks.json").read_text(encoding="utf-8"))
    if args.limit:
        samples = samples[: args.limit]

    print(f"Executor: {EXECUTOR_MODEL}")
    print(f"Evaluator: {EVALUATOR_MODEL}")
    print(f"样本数: {len(samples)}\n")

    results = []
    for i, s in enumerate(samples, 1):
        print(f"[{i}/{len(samples)}] {s['code']} {s.get('name', '')} ...", end=" ", flush=True)
        try:
            r = evaluate_sample(s)
            sc = r["scores"]
            print(
                f"acc={sc.get('data_accuracy', '?')} "
                f"cov={sc.get('logic_coverage', '?')} "
                f"invalid={sc.get('invalid_ratio_score', '?')} "
                f"({r['timing']['executor_s']}+{r['timing']['evaluator_s']}s)"
            )
            results.append(r)
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            results.append({"stock": s, "error": str(e)})

    valid = [r for r in results if "scores" in r]
    aggregates = {
        "data_accuracy": _mean(r["scores"].get("data_accuracy") for r in valid),
        "logic_coverage": _mean(r["scores"].get("logic_coverage") for r in valid),
        "invalid_ratio_score": _mean(r["scores"].get("invalid_ratio_score") for r in valid),
        "valid_n": len(valid),
        "total_n": len(samples),
    }

    print(f"\n=== 评估汇总 ({len(valid)}/{len(samples)} 成功) ===")
    print(json.dumps(aggregates, ensure_ascii=False, indent=2))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag_suffix = f"_{args.tag}" if args.tag else ""
    out_path = RESULTS_DIR / f"{ts}{tag_suffix}.json"
    out_path.write_text(
        json.dumps(
            {
                "tag": args.tag,
                "timestamp": ts,
                "executor_model": EXECUTOR_MODEL,
                "evaluator_model": EVALUATOR_MODEL,
                "aggregates": aggregates,
                "samples": results,
            },
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )
    print(f"\n详细结果: {out_path}")


if __name__ == "__main__":
    main()
