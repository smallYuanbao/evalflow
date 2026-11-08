import csv
import io
import json
from collections import defaultdict

from backend.db import SessionLocal
from backend.metrics import METRIC_LABELS, METRIC_ORDER
from backend.models import Dataset, DatasetItem, Generation, Run, Score, Trace


def _avg(vals):
    """求均值并保留 4 位小数。

    空列表返回 None,不返回 0:
      · 0   = 「评上了,但得分就是 0」
      · None = 「一条都没评上,没有数据」
    这两种情况在 judge 失败/覆盖率不足时必须能区分,否则均值会骗人。
    """
    return round(sum(vals) / len(vals), 4) if vals else None


def aggregate_run(run_id: int) -> dict:
    """把一次 run 的逐条分数聚合成 run 级指标。

    数据来源(三个表):
      · traces      —— 每条样本一行(问题/回答/证据)
      · scores      —— 每条样本的每个指标一行;judge 失败时 value=NULL
      · generations —— 每条样本的 token 与费用

    聚合分三步:
      1. 读数据:建立 trace→score、样本→分桶两个映射;
      2. 收集数值:按指标收集非 NULL 分数,同时按分桶再收集一份;
      3. 求均值 + 覆盖率:均值回答「多少分」,覆盖率回答「这个均值基于几条」。

    返回的 dict 同时供前端、门禁、分桶归因、模型对比使用。
    """
    # ---- ① 读 run 和这次 run 实际产生的 trace ----
    s = SessionLocal()
    run = s.get(Run, run_id)
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()
    # 注意:traces 是「实际跑了几条」,可能少于数据集条数(中途失败/部分成功)。
    # 所以后面的 item_count 用 len(traces),不是数据集的大小。

    # ---- ② 样本 id → 分桶 ----
    # 分桶存在 dataset_items 上;先一次性查成字典,避免在后面每条 trace 的循环里反复查库。
    item_ids = [tr.dataset_item_id for tr in traces]
    bucket_by_item = dict(
        s.query(DatasetItem.id, DatasetItem.bucket).filter(DatasetItem.id.in_(item_ids))
    ) if item_ids else {}

    # ---- ③ 把扁平的 Score 行折成嵌套字典 ----
    # 原始数据是「一行一个指标」:[(trace_id=1, name="recall", value=1.0), ...]
    # 折成 {1: {"recall": 1.0, "hit_at_k": 1.0, ...}, 2: {...}}
    # 后面的聚合都在这份嵌套字典上做,不用再碰数据库。
    score_by_trace = defaultdict(dict)
    if traces:
        for sc in s.query(Score).filter(Score.trace_id.in_([tr.id for tr in traces])):
            score_by_trace[sc.trace_id][sc.name] = sc.value

    # ---- ④ 费用汇总(Ch12):累加该 run 所有样本的 token 与费用 ----
    total_input = total_output = 0
    total_cost = 0.0
    if traces:
        for g in s.query(Generation).filter(Generation.trace_id.in_([tr.id for tr in traces])):
            total_input += g.input_tokens or 0
            total_output += g.output_tokens or 0
            total_cost += g.cost or 0.0
    s.close()  # 后面的计算全在内存里做,先把连接还掉

    # ---- ⑤ 这次 run 实际评了哪些指标 ----
    # 不硬编码指标名:从 score 行里收集,再按 metrics.py 的 METRIC_ORDER 排序。
    # 注册表里没有的指标(以后新加的)兜底排在最后,保证不会被静默丢掉。
    present = {name for tr in traces for name in score_by_trace.get(tr.id, {})}
    ordered = [m for m in METRIC_ORDER if m in present] + [m for m in present if m not in METRIC_ORDER]

    # ---- ⑥ 准备两个收集器 ----
    # overall: 每个指标一个列表,存所有样本的分数
    # buckets: 每个分桶 × 每个指标一个列表
    # count_by_bucket: 每个分桶有几条 trace(分母/展示用)
    overall = {m: [] for m in ordered}
    buckets = defaultdict(lambda: {m: [] for m in ordered})
    count_by_bucket = defaultdict(int)

    # 逐条 trace 把分数放进对应的列表:
    #   · v is not None → 才收;NULL(judge 失败)跳过,不记 0
    #   · 同一条 trace 会同时进 overall 和它所属分桶的列表
    for tr in traces:
        b = bucket_by_item.get(tr.dataset_item_id, "未分桶")
        count_by_bucket[b] += 1
        for m in ordered:
            v = score_by_trace.get(tr.id, {}).get(m)
            if v is not None:
                overall[m].append(v)
                buckets[b][m].append(v)

    # ---- ⑦ 分桶聚合 ----
    # 对每个分桶、每个指标求均值,并把该桶的样本数 count 一起带上。
    # 注意三点:
    #   1) 这是「桶内样本的简单平均」,不是把各桶均值再平均;
    #   2) count 是实际跑了几条 trace,不是数据集里该桶的条数;
    #   3) 某指标在该桶内全是 NULL 时,_avg 返回 None,不会被误写成 0。
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
        # ---- ⑧ 整体结果 ----
        # item_count:实际产生的 trace 数;如果小于数据集条数,说明这次没跑完整。
        "item_count": len(traces),
        # scores:每个指标在所有样本上的均值;库里没有的指标不会出现在这里。
        "scores": {m: _avg(overall[m]) for m in ordered},
        # ---- ⑨ 覆盖率:这个均值是基于几条算出来的 ----
        # judge 失败不是「不写 Score」,而是写一行 value=NULL。
        # 所以:
        #   attempted = 有几条 trace **存在**该指标的行(应该评几条)
        #   scored    = 其中 value 非 NULL 的(真的评上了几条)
        #
        # 为什么必须露出来:
        #   20 条样本里挂了 17 条 judge → 均值只由剩下 3 条算出来。
        #   挂掉的往往是最长/最难的样本,所以均值会系统性偏乐观。
        #   只看 0.9 会误以为「20 条都很好」,看 3/20 才知道样本不足。
        #
        # 例(run #22):
        #   recall   → 15/15(只有库内题有这项)
        #   rejection→ 4/4 (只有库外题有这项)
        #   注意 attempted 不等于 item_count:不同指标覆盖的题目范围不同。
        "score_coverage": {
            m: {
                "scored": len(overall[m]),
                "attempted": sum(1 for tr in traces if m in score_by_trace.get(tr.id, {})),
            }
            for m in ordered
        },
        # ---- ⑩ 分桶结果 ----
        # 结构:{ "护理": {"count": 4, "recall": 0.5, ...}, "喂养": {...}, ... }
        # 用途:门禁说「整体掉了」之后,归因接口拿它对比两个 run,
        #       定位是哪个桶掉的;前端也用它画分桶柱状图。
        # 某个桶没有某指标(例如库外桶没有 recall)时,该指标的值是 None。
        "by_bucket": by_bucket,
        # ---- ⑪ 费用 ----
        # 来自 generations 表,只统计「evalflow 自己调 LLM」的 token;
        # 被测系统(baby-ai)自己烧的 token 不在里面。
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost": round(total_cost, 6),
    }


def dataset_comparability(run_a_id: int, run_b_id: int) -> dict:
    """两次 run 的评测集是不是「同一批题」——这是分数能不能直接比的前提(Ch29)。

    `dataset_hash` 覆盖 (input, expected_output, bucket):任何一条样本增删改都会变,
    所以它比手写的 version 号可靠(version 要靠人记得 bump,容易和实际漂移)。

    拿两个不同版本的评测集算出的均值去比,**比的是两个不同的东西**——
    门禁会报出「回归」,而它其实是「换了一批题」。

    返回 comparable:
      · True  —— hash 一致,可以比
      · False —— 不一致(附题目数与 hash 前缀,便于定位)
      · None  —— 至少一方是早期 run、快照里没有 hash → **显式说不知道,不假装能比**
    """
    s = SessionLocal()
    runs = {r.id: r for r in s.query(Run).filter(Run.id.in_([run_a_id, run_b_id]))}
    s.close()
    a, b = runs.get(run_a_id), runs.get(run_b_id)
    if a is None or b is None:
        return {"comparable": None, "reason": "run 不存在"}

    def _cfg(r: Run) -> dict:
        try:
            return json.loads(r.config or "{}")
        except json.JSONDecodeError:
            return {}

    ca, cb = _cfg(a), _cfg(b)
    ha, hb = ca.get("dataset_hash"), cb.get("dataset_hash")
    if not ha or not hb:
        return {"comparable": None,
                "reason": "有一方是早期 run、快照里没有 dataset_hash,无法判断是不是同一批题"}
    if ha == hb:
        return {"comparable": True, "reason": None}
    return {
        "comparable": False,
        "reason": (f"两次 run 的评测集不同({ca.get('item_count')} 条 vs {cb.get('item_count')} 条,"
                   f"hash {ha[:8]} vs {hb[:8]}),分数不可直接比较"),
    }


def runs_trend(limit: int = 50, dataset_id: int | None = None) -> list[dict]:
    """历史指标趋势(Ch13):批量聚合最近 N 个 run 的 per-metric 均值。

    一次查询所有 trace/score 再按 run 分组,避免前端逐 run 拉(那会 N+1)。
    dataset_id(Ch21):只看某个评测集的趋势,不传=全部。
    """
    s = SessionLocal()
    q = s.query(Run).order_by(Run.id.desc())
    if dataset_id is not None:
        q = q.filter(Run.dataset_id == dataset_id)
    runs = q.limit(limit).all()
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


def _csv_line(cells: list) -> str:
    """把一行 cells 渲染成 CSV 文本(含换行符),含逗号/引号/换行的字段自动加引号转义。"""
    buf = io.StringIO()
    csv.writer(buf).writerow(cells)
    return buf.getvalue()


def run_export_csv_stream(run_id: int):
    """流式产出 CSV(Ch25):逐行 yield,内存不随总行数增长。

    为什么必须流式:原实现把全部 Trace 用 .all() 拉进内存、再拼成整份字符串——样本一多,
    后端内存是 CSV 大小的 2~3 倍。这里改为:
      · 分数是小标量(trace_id/name/value),一次取走不心疼;
      · 真正占内存的 trace 正文(input/output)用 yield_per 分批取,一次只驻留一批。
    """
    s = SessionLocal()
    try:
        score_by_trace: dict[int, dict] = defaultdict(dict)
        for tid, name, value in (
            s.query(Score.trace_id, Score.name, Score.value)
            .join(Trace, Score.trace_id == Trace.id)
            .filter(Trace.run_id == run_id)
        ):
            score_by_trace[tid][name] = value

        present = {n for d in score_by_trace.values() for n in d}
        metrics = [m for m in METRIC_ORDER if m in present] + [m for m in present if m not in METRIC_ORDER]

        yield _csv_line(["样本ID", "问题", "回答", "耗时(ms)"] + [METRIC_LABELS.get(m, m) for m in metrics])

        # yield_per:分批从库里取,不在内存里堆积整表的正文
        for t in s.query(Trace).filter(Trace.run_id == run_id).order_by(Trace.id).yield_per(500):
            sc = score_by_trace.get(t.id, {})
            yield _csv_line([t.id, t.input, t.output, t.latency_ms] + [sc.get(m, "") for m in metrics])
    finally:
        s.close()
