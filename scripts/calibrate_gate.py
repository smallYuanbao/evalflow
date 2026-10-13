"""门禁阈值校准(Ch28):用「同配置重跑」的实测分布,推 GATE_RULES 的 min / max_regression。

对齐 MewHelp 的 `calibrate-confidence` 思路(阈值由评估集校准回填,不拍脑袋),
但方法不同:那边是**二分类**问题(扫阈值取 Youden J 最大的分离点),
这里量的是**连续质量**,没有「应通过/应拒绝」的标签,所以改为——

  用「什么都没变时的自然波动」当噪声底:
    · max_regression 必须 **大于** 噪声,否则门禁天天误报;
    · min 取健康基线的低位,留出同样的余量。

为什么要「同配置重跑」而不是查文档:门禁比较的是**两次 run**,
而每次 run 都会重新生成回答 —— 生成随机性本身就是噪声的一部分,必须实测。

用法:
    uv run python scripts/calibrate_gate.py <dataset_id> [--runs 12,13,14]

**产物是建议值,不是自动生效**——和 MewHelp 一样,人工确认后回填 gate.py。
n 小的时候结论粗糙,脚本会显式提醒。
"""
import argparse
import json
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from backend.db import SessionLocal  # noqa: E402
from backend.gate import GATE_RULES  # noqa: E402
from backend.models import Run  # noqa: E402
from backend.stats import aggregate_run  # noqa: E402

# 安全系数:实测极差再放宽一点,避免「刚好卡在边界」反复横跳
RANGE_SAFETY = 1.3


def collect(dataset_id: int, run_ids: list[int] | None) -> dict[int, dict]:
    s = SessionLocal()
    if run_ids:
        ids = run_ids
    else:
        ids = [r.id for r in s.query(Run).filter(Run.dataset_id == dataset_id, Run.status == "done")
               .order_by(Run.id.desc()).limit(5)]
        ids.reverse()
    s.close()
    return {rid: aggregate_run(rid)["scores"] for rid in ids}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset_id", type=int)
    ap.add_argument("--runs", help="逗号分隔的 run id;不传则取最近 5 个 done")
    a = ap.parse_args()
    ids = [int(x) for x in a.runs.split(",")] if a.runs else None

    scores = collect(a.dataset_id, ids)
    if len(scores) < 2:
        print("至少需要 2 次同配置 run 才能估噪声。先多跑几次(同数据集、同配置)。")
        return
    n = len(scores)
    print(f"用 {n} 次同配置 run: {list(scores)}\n")

    metrics = [m for m in GATE_RULES if any(scores[r].get(m) is not None for r in scores)]
    print(f"{'指标':22s}{'均值':>8s}{'最小':>8s}{'最大':>8s}{'极差':>8s}{'建议 min':>10s}{'建议容忍':>10s}{'现容忍':>8s}")
    print("-" * 90)
    suggestion = {}
    for m in metrics:
        vs = [scores[r][m] for r in scores if scores[r].get(m) is not None]
        if len(vs) < 2:
            continue
        mean, lo, hi = st.mean(vs), min(vs), max(vs)
        rng = hi - lo
        # 容忍度 = 实测极差 × 安全系数(至少 0.02,避免机械指标被压成 0)
        tol = max(round(rng * RANGE_SAFETY, 3), 0.02)
        # 下限 = 最小值再往下留同样的余量
        floor = round(lo - tol, 3)
        suggestion[m] = {"min": max(floor, 0.0), "max_regression": tol}
        cur = GATE_RULES.get(m, {}).get("max_regression", "—")
        print(f"{m:22s}{mean:>8.3f}{lo:>8.3f}{hi:>8.3f}{rng:>8.3f}{max(floor,0.0):>10.3f}{tol:>10.3f}{cur:>8}")

    print("\n建议回填 backend/gate.py:")
    print("GATE_RULES = " + json.dumps(suggestion, ensure_ascii=False, indent=4))

    print(f"\n⚠ n={n} 次 run 估出的「极差」本身有 ~{100/ (2*(n-1))**0.5:.0f}% 量级的相对误差。")
    print("  要收紧阈值,先把 run 次数加多(或把数据集扩到上百条)——别拿 3 次的极差当精确值。")


if __name__ == "__main__":
    main()
