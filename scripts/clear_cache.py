"""清理项目持久化磁盘缓存（.cache/ 目录）。

用法：
    python -m scripts.clear_cache             # 清全部
    python -m scripts.clear_cache --keep-sw   # 保留申万行业索引（构建慢，单独清理意义不大）
"""
import argparse
import shutil
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-sw", action="store_true",
                        help="保留申万行业相关缓存（_ak_sw_first_info / _ak_index_component_sw）")
    args = parser.parse_args()

    if not CACHE_DIR.exists():
        print("没有发现 .cache/ 目录，跳过")
        return

    sub = CACHE_DIR / "joblib"
    if not sub.exists():
        print(f"{CACHE_DIR} 为空")
        return

    total_before = sum(f.stat().st_size for f in CACHE_DIR.rglob("*") if f.is_file())
    deleted = 0

    for func_dir in sub.rglob("_ak_*"):
        if not func_dir.is_dir():
            continue
        name = func_dir.name
        if args.keep_sw and ("sw_first_info" in name or "index_component_sw" in name):
            print(f"  保留 {name}")
            continue
        size = sum(f.stat().st_size for f in func_dir.rglob("*") if f.is_file())
        shutil.rmtree(func_dir)
        deleted += size
        print(f"  清除 {name}  ({size/1024/1024:.1f} MB)")

    print(f"\n释放 {deleted/1024/1024:.1f} MB（清前 {total_before/1024/1024:.1f} MB）")


if __name__ == "__main__":
    main()
