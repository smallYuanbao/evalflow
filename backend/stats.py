from collections import defaultdict

from backend.db import SessionLocal
from backend.metrics import METRIC_ORDER
from backend.models import DatasetItem, Run, Score, Trace


def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate_run(run_id: int) -> dict:
    """聚合一次 run 的分数:按指标注册表动态遍历(不再硬编码指标名)。judge 挂(NULL)不参与均值。"""
    s = SessionLocal()
    run = s.get(Run, run_id)
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()

    item_ids = [tr.dataset_item_id for tr in traces]
    bucket_by_item = dict(
        s.query(DatasetItem.id, DatasetItem.bucket).filter(DatasetItem.id.in_(item_ids))
    ) if item_ids else {}

    score_by_trace = defaultdict(dict)
    if traces:
        for sc in s.query(Score).filter(Score.trace_id.in_([tr.id for tr in traces])):
            score_by_trace[sc.trace_id][sc.name] = sc.value
    s.close()

    # 动态收集「实际评过」的指标名,按注册表顺序排;注册表外的兜底排最后(未知指标不丢)
    present = {name for tr in traces for name in score_by_trace.get(tr.id, {})}
    ordered = [m for m in METRIC_ORDER if m in present] + [m for m in present if m not in METRIC_ORDER]

    overall = {m: [] for m in ordered}
    buckets = defaultdict(lambda: {m: [] for m in ordered})
    count_by_bucket = defaultdict(int)
    for tr in traces:
        b = bucket_by_item.get(tr.dataset_item_id, "未分桶")
        count_by_bucket[b] += 1
        for m in ordered:
            v = score_by_trace.get(tr.id, {}).get(m)
            if v is not None:
                overall[m].append(v)
                buckets[b][m].append(v)

    by_bucket = {
        b: {"count": count_by_bucket[b], **{m: _avg(buckets[b][m]) for m in ordered}}
        for b in buckets
    }

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "config": run.config,
        "progress": run.progress,
        "item_count": len(traces),
        "scores": {m: _avg(overall[m]) for m in ordered},
        "by_bucket": by_bucket,
    }
