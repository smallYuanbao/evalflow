from collections import defaultdict

from backend.db import SessionLocal
from backend.models import DatasetItem, Run, Score, Trace


def _avg(vals):
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate_run(run_id: int) -> dict:
    """聚合一次 run 的分数:整体均值 + 按 bucket 分组均值。judge 挂(NULL)不参与均值。"""
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

    overall = {"recall": [], "faithfulness": [], "rejection": []}
    buckets = defaultdict(lambda: {"recall": [], "faithfulness": [], "rejection": []})
    count_by_bucket = defaultdict(int)
    for tr in traces:
        b = bucket_by_item.get(tr.dataset_item_id, "未分桶")
        count_by_bucket[b] += 1
        for key in ("recall", "faithfulness", "rejection"):
            v = score_by_trace.get(tr.id, {}).get(key)
            if v is not None:
                overall[key].append(v)
                buckets[b][key].append(v)

    by_bucket = {
        b: {
            "count": count_by_bucket[b],
            "recall_avg": _avg(buckets[b]["recall"]),
            "faithfulness_avg": _avg(buckets[b]["faithfulness"]),
            "rejection_rate": _avg(buckets[b]["rejection"]),
        }
        for b in buckets
    }

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "config": run.config,
        "item_count": len(traces),
        "scores": {
            "recall_avg": _avg(overall["recall"]),
            "faithfulness_avg": _avg(overall["faithfulness"]),
            "rejection_rate": _avg(overall["rejection"]),
        },
        "by_bucket": by_bucket,
    }
