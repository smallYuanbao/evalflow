import csv
import io
from collections import defaultdict

from backend.db import SessionLocal
from backend.metrics import METRIC_ORDER
from backend.models import Dataset, DatasetItem, Generation, Run, Score, Trace


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

    # 费用汇总(Ch12):累加该 run 所有样本的 token 与费用
    total_input = total_output = 0
    total_cost = 0.0
    if traces:
        for g in s.query(Generation).filter(Generation.trace_id.in_([tr.id for tr in traces])):
            total_input += g.input_tokens or 0
            total_output += g.output_tokens or 0
            total_cost += g.cost or 0.0
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
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost": round(total_cost, 6),
    }


def runs_trend(limit: int = 50) -> list[dict]:
    """历史指标趋势(Ch13):批量聚合最近 N 个 run 的 per-metric 均值。

    一次查询所有 trace/score 再按 run 分组,避免前端逐 run 拉(那会 N+1)。
    """
    s = SessionLocal()
    runs = s.query(Run).order_by(Run.id.desc()).limit(limit).all()
    runs = list(reversed(runs))  # 时间正序:折线图从左到右
    if not runs:
        s.close()
        return []

    traces = s.query(Trace).filter(Trace.run_id.in_([r.id for r in runs])).all()
    traces_by_run = defaultdict(list)
    for t in traces:
        traces_by_run[t.run_id].append(t.id)

    score_by_trace = defaultdict(dict)
    if traces:
        for sc in s.query(Score).filter(Score.trace_id.in_([t.id for t in traces])):
            score_by_trace[sc.trace_id][sc.name] = sc.value

    names = dict(s.query(Dataset.id, Dataset.name).filter(
        Dataset.id.in_({r.dataset_id for r in runs})))
    s.close()

    out = []
    for r in runs:
        by_metric = defaultdict(list)
        for tid in traces_by_run.get(r.id, []):
            for name, v in score_by_trace.get(tid, {}).items():
                if v is not None:  # NULL(judge 挂)不参与均值,与 aggregate_run 一致
                    by_metric[name].append(v)
        out.append({
            "id": r.id,
            "dataset_id": r.dataset_id,
            "dataset_name": names.get(r.dataset_id),
            "status": r.status,
            "created_at": r.created_at,
            "scores": {m: _avg(vals) for m, vals in by_metric.items() if vals},
        })
    return out


def run_export_csv(run_id: int) -> str:
    """导出某 run 的逐 trace 明细为 CSV(Ch13 供外部分析)。空 run 返回空串。"""
    s = SessionLocal()
    traces = s.query(Trace).filter(Trace.run_id == run_id).order_by(Trace.id).all()
    if not traces:
        s.close()
        return ""
    score_by_trace = defaultdict(dict)
    for sc in s.query(Score).filter(Score.trace_id.in_([t.id for t in traces])):
        score_by_trace[sc.trace_id][sc.name] = sc.value
    s.close()

    # 指标列 = 该 run 实际出现的指标,按注册表顺序(与 aggregate_run 一致)
    present = {name for t in traces for name in score_by_trace.get(t.id, {})}
    metrics = [m for m in METRIC_ORDER if m in present] + [m for m in present if m not in METRIC_ORDER]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["trace_id", "input", "output", "latency_ms"] + metrics)
    for t in traces:
        w.writerow([t.id, t.input, t.output, t.latency_ms]
                   + [score_by_trace.get(t.id, {}).get(m, "") for m in metrics])
    return buf.getvalue()
