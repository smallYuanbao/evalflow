"""裁判自复现性(Ch28):同一个裁判把同一批 trace 重复打 K 次,分数会变吗?

这是噪声图的第三块(前两块:生成随机性、跨裁判差异)。它回答一个很基础的问题:
**裁判本身是确定的,还是每次都在抖?**

- 若抖动 ≈ 0 → 裁判是「确定的仪器」,噪声全来自「选哪个模型」→ 固定裁判就能锁死测量;
- 若抖动明显 → 又多了第三个噪声源,重复采样取均值(judge_samples>1)才有意义。

不需要新 key,只重打分,不动被测系统。

用法:
    uv run python -u scripts/judge_repeat.py <run_id> [--k 3]
"""
import argparse
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from backend import evaluators  # noqa: E402
from backend.db import SessionLocal  # noqa: E402
from backend.models import DatasetItem, Score, Trace  # noqa: E402

JUDGE_FNS = {
    "faithfulness": lambda t, exp: evaluators.faithfulness(t.output, t.retrieved_context),
    "context_precision": lambda t, exp: evaluators.context_precision(t.input, t.retrieved_context),
    "context_recall": lambda t, exp: evaluators.context_recall(t.input, exp, t.retrieved_context),
    "answer_relevance": lambda t, exp: evaluators.answer_relevance(t.input, t.output),
    "answer_correctness": lambda t, exp: evaluators.answer_correctness(t.input, exp, t.output),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id", type=int)
    ap.add_argument("--k", type=int, default=3, help="每个指标重复打分次数")
    a = ap.parse_args()

    s = SessionLocal()
    rows = (s.query(Trace, DatasetItem)
            .join(DatasetItem, Trace.dataset_item_id == DatasetItem.id)
            .filter(Trace.run_id == a.run_id).all())
    s.close()
    rows = [(t, it) for t, it in rows if it.bucket != "库外"]
    print(f"Run {a.run_id}:{len(rows)} 条库内样本 × {len(JUDGE_FNS)} 指标 × K={a.k},"
          f"共 {len(rows) * len(JUDGE_FNS) * a.k} 次调用\n", flush=True)

    # per_metric[metric] = [(原分, [K 次重复分]), ...]
    per_metric: dict[str, list[tuple[float | None, list[float]]]] = defaultdict(list)
    for idx, (t, it) in enumerate(rows, 1):
        for name, fn in JUDGE_FNS.items():
            reps = []
            for _ in range(a.k):
                r = fn(t, it.expected_output)
                if r is not None:
                    reps.append(r["score"])
            if reps:
                per_metric[name].append((None, reps))
        print(f"  [{idx}/{len(rows)}] {t.input[:16]}", flush=True)

    print(f"\n{'指标':22s}{'n':>4s}{'同分率':>9s}{'最大抖动':>10s}{'平均抖动':>10s}")
    print("-" * 58)
    for name, items in per_metric.items():
        stable = sum(1 for _, reps in items if len(set(reps)) == 1)
        max_spread = max(max(reps) - min(reps) for _, reps in items)
        mean_spread = st.mean(max(reps) - min(reps) for _, reps in items)
        print(f"{name:22s}{len(items):>4d}{stable / len(items):>8.0%}"
              f"{max_spread:>10.3f}{mean_spread:>10.3f}")

    print("\n对照:门禁容忍度 max_regression = 0.05")
    print("同分率 100% 且抖动 0 → 裁判是确定的仪器,噪声全来自「选哪个模型」。")


if __name__ == "__main__":
    main()
