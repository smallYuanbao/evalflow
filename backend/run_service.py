import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend import llm
from backend.config import settings
from backend.db import SessionLocal
from backend.evaluators import (
    answer_correctness,
    answer_relevance,
    context_precision,
    context_recall,
    faithfulness,
    hit_at_k,
    mrr,
    recall,
    rejected,
)
from backend.models import DatasetItem, Generation, Run, Score, Trace
from backend.pipeline import run_pipeline
from backend.snapshot import config_retrieval, config_top_k

logger = logging.getLogger(__name__)

ABSENT_BUCKET = "库外"  # 库外题:知识库里没有答案,正确行为是拒答

if settings.e2e_mock:
    # E2E 下替换 pipeline 与 5 个 LLM judge 为确定性假实现(Ch14);recall/rejected 是机械基线,保持真实
    from backend.e2e_mock import mock_judge, mock_run_pipeline

    run_pipeline = mock_run_pipeline
    faithfulness = context_precision = context_recall = answer_relevance = answer_correctness = mock_judge
elif settings.eval_target == "babyai":
    # 被测系统换成真实 RAG 应用 baby-ai(Ch26):只换「取回答」这一步,
    # judge 仍用 EvalFlow 自己的——评的是 baby-ai 的输出,不是把裁判也交出去。
    from backend.external_babyai import run_pipeline_babyai

    run_pipeline = run_pipeline_babyai


def execute_run(run_id: int) -> None:
    """并发调度:线程池并发跑样本,主线程收结果更新进度;全成 done,任一异常 failed。

    注:与旧串行版不同,失败时已完成样本的 Trace 会保留(部分结果),便于定位挂在哪条。
    """
    s = SessionLocal()
    run = s.get(Run, run_id)
    if run is None:
        s.close()
        return
    top_k = config_top_k(run.config)
    retrieval = config_retrieval(run.config)
    rows = s.query(DatasetItem).filter(DatasetItem.dataset_id == run.dataset_id).all()
    # 提前取出普通字段:commit 会让 ORM 对象 expire,detached 后访问会 DetachedInstanceError
    items = [(it.id, it.input, it.expected_output, it.bucket) for it in rows]
    run.progress = 0
    s.commit()
    s.close()

    logger.info("run 开始执行", extra={"run_id": run_id})
    t0 = time.time()

    def _mark(status: str) -> None:
        s = SessionLocal()
        s.get(Run, run_id).status = status
        s.commit()
        s.close()

    if not items:
        _mark("done")
        logger.info("run 执行完成", extra={"run_id": run_id,
                                           "duration_ms": int((time.time() - t0) * 1000)})
        return

    try:
        with ThreadPoolExecutor(max_workers=max(1, settings.run_concurrency)) as pool:
            futures = [
                pool.submit(_process_item, run_id, iid, inp, exp, bkt, top_k, retrieval)
                for (iid, inp, exp, bkt) in items
            ]
            for done in as_completed(futures):
                done.result()  # 样本抛异常 → 整个 run 失败(与旧语义一致)
                _bump_progress(run_id)
        _mark("done")
        logger.info("run 执行完成", extra={"run_id": run_id,
                                           "duration_ms": int((time.time() - t0) * 1000)})
    except Exception:
        logger.exception("run 执行失败", extra={"run_id": run_id,
                                                "duration_ms": int((time.time() - t0) * 1000)})
        _mark("failed")


def _process_item(run_id: int, item_id: int, input_: str, expected_output: str,
                  bucket: str, top_k: int, retrieval: str) -> None:
    """单样本评测:检索 + 生成 + 打分 + 写 Trace/Score(独立 session,线程安全)。

    LLM judge 在开 session 前算完:写锁跨 LLM 调用时,并发写 SQLite 会 database is locked。
    """
    llm.reset_usage()  # 本样本 token 计量归零(线程复用也能正确隔离)
    t0 = time.time()
    out = run_pipeline(input_, top_k, retrieval=retrieval)
    latency_ms = int((time.time() - t0) * 1000)
    hits = [{"text": h["text"], "score": h["score"], "rank": i + 1}
            for i, h in enumerate(out["hits"])]

    # 5 个 LLM judge 提前算(不持 DB 写锁);库外题只评拒答,无 judge
    judges = [] if bucket == ABSENT_BUCKET else [
        ("context_precision", context_precision(input_, out["retrieved_context"])),
        ("context_recall", context_recall(input_, expected_output, out["retrieved_context"])),
        ("faithfulness", faithfulness(out["output"], out["retrieved_context"])),
        ("answer_relevance", answer_relevance(input_, out["output"])),
        ("answer_correctness", answer_correctness(input_, expected_output, out["output"])),
    ]

    # 本样本「生成 + judge」累计的 token 与费用(算完再开 session,保持事务短)
    prompt_tokens, completion_tokens = llm.get_usage()
    cost = round(llm.compute_cost(prompt_tokens, completion_tokens), 6)

    s = SessionLocal()
    tr = Trace(run_id=run_id, dataset_item_id=item_id,
               input=input_, output=out["output"],
               retrieved_context=out["retrieved_context"],
               retrieval_hits=json.dumps(hits, ensure_ascii=False),
               latency_ms=latency_ms)
    s.add(tr)
    s.flush()
    trace_id = tr.id  # commit 会让 ORM 对象 expire,提前取普通字段(Ch10 坑 #2)
    s.add(Generation(trace_id=trace_id, model=settings.chat_model,
                     input_tokens=prompt_tokens, output_tokens=completion_tokens, cost=cost))
    if bucket == ABSENT_BUCKET:
        # 库外题:只评「拒答」(正确行为是不答)
        s.add(Score(trace_id=tr.id, name="rejection", value=rejected(out["output"])))
    else:
        # recall 机械基线(确定性,0 次 LLM)
        s.add(Score(trace_id=tr.id, name="recall",
                    value=recall(expected_output, out["retrieved_context"])))
        # 检索质量机械指标(Ch20):hit@k / MRR,从有序 hits 算,同样不烧 LLM
        s.add(Score(trace_id=tr.id, name="hit_at_k", value=hit_at_k(expected_output, out["hits"])))
        s.add(Score(trace_id=tr.id, name="mrr", value=mrr(expected_output, out["hits"])))
        for name, r in judges:
            if r is None:
                s.add(Score(trace_id=tr.id, name=name, value=None, comment="judge 失败"))
            else:
                s.add(Score(trace_id=tr.id, name=name, value=r["score"],
                            variance=r.get("variance"), comment=r["reason"]))
    s.commit()
    s.close()
    logger.info("样本评测完成", extra={"run_id": run_id, "trace_id": trace_id, "latency_ms": latency_ms})


def _bump_progress(run_id: int) -> None:
    """进度自增(原子 UPDATE progress = progress + 1,避免并发读-改-写竞争)。"""
    s = SessionLocal()
    s.query(Run).filter(Run.id == run_id).update(
        {Run.progress: Run.progress + 1}, synchronize_session=False)
    s.commit()
    s.close()
