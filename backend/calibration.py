"""Judge 校准(Ch18):比对 judge 分与人工金标准分,算 bias / MAE / Pearson / n。

校准 = 在带 gold 标注的数据集上跑 run,比较 judge 分 vs 金标准分。复用现有 run 机制,
judge 走和生产完全相同的流程,结果才有代表性。gold 存在 DatasetItem.gold_scores(JSON)。
"""
import json
from collections import defaultdict

from backend.db import SessionLocal
from backend.models import DatasetItem, Run, Score, Trace


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson 相关系数:n<2 或方差为 0 时无定义,返回 None(小样本噪声大,仅供参考)。"""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / (vx ** 0.5 * vy ** 0.5)


def calibrate(judge: dict[str, list[float]], gold: dict[str, list[float]]) -> dict:
    """纯函数:对每个 metric 的 (judge, gold) 序列算 bias / MAE / Pearson / n。

    bias = judge 均值 − gold 均值(系统性偏松/偏严,最可操作);MAE = 平均绝对误差;
    Pearson = 排序一致性;n = 校准样本数。
    """
    out = {}
    for m, js in judge.items():
        gs = gold.get(m, [])
        n = len(js)
        diffs = [j - g for j, g in zip(js, gs)]
        bias = round(sum(diffs) / n, 4) if n else None
        mae = round(sum(abs(d) for d in diffs) / n, 4) if n else None
        p = _pearson(js, gs)
        out[m] = {
            "bias": bias,
            "mae": mae,
            "corr": round(p, 4) if p is not None else None,
            "n": n,
        }
    return out


def calibration_report(run_id: int) -> dict | None:
    """拉 run 的 trace + item 金标准 + judge 分,组装成校准报告;run 不存在返回 None。"""
    s = SessionLocal()
    run = s.get(Run, run_id)
    if run is None:
        s.close()
        return None
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()

    item_ids = [t.dataset_item_id for t in traces]
    gold_by_item: dict[int, dict] = {}
    if item_ids:
        for it in s.query(DatasetItem).filter(DatasetItem.id.in_(item_ids)):
            if it.gold_scores:
                try:
                    gold_by_item[it.id] = json.loads(it.gold_scores)
                except json.JSONDecodeError:
                    pass  # 金标准 JSON 坏了就跳过这条

    tids = [t.id for t in traces]
    judge_by_trace: dict[int, dict] = defaultdict(dict)
    if tids:
        for sc in s.query(Score).filter(Score.trace_id.in_(tids)):
            judge_by_trace[sc.trace_id][sc.name] = sc.value
    s.close()

    judge_lists: dict[str, list[float]] = defaultdict(list)
    gold_lists: dict[str, list[float]] = defaultdict(list)
    for t in traces:
        gold = gold_by_item.get(t.dataset_item_id)
        jsc = judge_by_trace.get(t.id, {})
        if not gold:
            continue
        for m, gv in gold.items():
            jv = jsc.get(m)
            if jv is None:
                continue  # 该 metric 没被 judge 评上(挂/库外),不参与校准
            judge_lists[m].append(jv)
            gold_lists[m].append(gv)

    return {"run_id": run_id, "metrics": calibrate(judge_lists, gold_lists)}
