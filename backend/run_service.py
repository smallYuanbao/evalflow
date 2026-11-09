import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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
    rejection_dual,
)
from backend.models import DatasetItem, Generation, Run, Score, Trace
from backend.pipeline import run_pipeline
from backend.snapshot import config_retrieval, config_top_k

logger = logging.getLogger(__name__)

ABSENT_BUCKET = "库外"  # 库外题:知识库里没有答案,正确行为是拒答

HEARTBEAT_INTERVAL_SECONDS = 10


def _now_str() -> str:
    """与 models._now 同一格式(本地时间、秒级),保证可以和 created_at 直接比较。"""
    return datetime.now().isoformat(timespec="seconds")


class _RunHeartbeat:
    """run 执行期间定时刷新 `runs.last_heartbeat_at`。

    为什么不能拿 progress 当心跳:单条样本要跑「检索 + 生成 + 5 个 judge」,
    可能几分钟 progress 都不变;按 progress 超时回收会把正在跑的 run 误杀。
    """

    def __init__(self, run_id: int):
        self.run_id = run_id
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name=f"run-heartbeat-{run_id}", daemon=True
        )

    @staticmethod
    def _touch(run_id: int) -> None:
        s = SessionLocal()
        try:
            s.query(Run).filter(Run.id == run_id).update(
                {Run.last_heartbeat_at: _now_str()}, synchronize_session=False
            )
            s.commit()
        except Exception as e:
            # 心跳失败不能影响主流程;下一轮会重试
            logger.warning("run 心跳写入失败: %s", e, extra={"run_id": run_id})
        finally:
            s.close()

    def _loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            self._touch(self.run_id)

    def start(self) -> None:
        # 立即写一次:覆盖「刚启动、还没到第一个心跳周期」的窗口
        self._touch(self.run_id)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

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
elif settings.eval_target == "ecom":
    # Ch07：被测系统换成 ecom-agent，走它的非流式评测门面。
    from backend.external_ecom import run_pipeline_ecom

    run_pipeline = run_pipeline_ecom


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

    # 心跳独立于进度:单条样本可能跑几分钟,progress 不动不代表 run 死了。
    heartbeat = _RunHeartbeat(run_id)
    heartbeat.start()
    _touch_progress(run_id)  # 进度超时的起点
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
    finally:
        heartbeat.stop()


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

    context = str(out.get("retrieved_context") or "")
    has_context = bool(context.strip()) and context.strip() != "(无证据)"

    # LLM judge 提前算(不持 DB 写锁);库外题只评拒答。
    # 无检索上下文的样本（B/C/E 出口）跳过 context/faithfulness，
    # 否则会拿「(无证据)」去问 judge，分数没有意义。
    judges = []
    if bucket != ABSENT_BUCKET:
        if has_context:
            judges.extend(
                [
                    ("context_precision", context_precision(input_, context)),
                    ("context_recall", context_recall(input_, expected_output, context)),
                    ("faithfulness", faithfulness(out["output"], context)),
                ]
            )
        judges.extend(
            [
                ("answer_relevance", answer_relevance(input_, out["output"])),
                ("answer_correctness", answer_correctness(input_, expected_output, out["output"])),
            ]
        )

    # 库外题:拒答双信号(词表 + LLM judge)。和上面的 judge 一样在开 DB session 前算完——
    # 把一次 LLM 调用夹在写事务里,并发时会撞 SQLite 的 database is locked。
    # E2E 必须确定性且不联网,所以只走词表信号(与 Ch14 的 mock 语义一致)。
    rejection_value: float | None = None
    rejection_comment = ""
    if bucket == ABSENT_BUCKET:
        if settings.e2e_mock:
            rejection_value = rejected(out["output"])
            rejection_comment = "E2E:仅词表信号"
        else:
            rejection_value, rejection_comment = rejection_dual(input_, out["output"])

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
        # 库外题:只评「拒答」(正确行为是不答);值与判定依据都落库
        s.add(Score(trace_id=tr.id, name="rejection", value=rejection_value,
                    comment=rejection_comment))
    else:
        # 机械指标只写「适用」的样本：B2–B7 没有回答证据，
        # 不写 recall / hit@k / MRR 行，而不是写 NULL。
        # 这样 score_coverage 才是「10/10 评上了」，不会被读成「44 条漏了 34 条」。
        # C 出口可能检索到 policy，但那些 hits 不是回答证据，同样不算。
        if has_context:
            s.add(Score(trace_id=tr.id, name="recall",
                        value=recall(expected_output, context)))
            s.add(Score(trace_id=tr.id, name="hit_at_k",
                        value=hit_at_k(expected_output, out["hits"])))
            s.add(Score(trace_id=tr.id, name="mrr",
                        value=mrr(expected_output, out["hits"])))
        for name, r in judges:
            if r is None:
                s.add(Score(trace_id=tr.id, name=name, value=None, comment="judge 失败"))
            else:
                s.add(Score(trace_id=tr.id, name=name, value=r["score"],
                            variance=r.get("variance"), comment=r["reason"]))
    s.commit()
    s.close()
    logger.info("样本评测完成", extra={"run_id": run_id, "trace_id": trace_id, "latency_ms": latency_ms})


def _touch_progress(run_id: int) -> None:
    """记录「开始执行」的时间:进度超时判定需要一个起点(否则 progress=0 时没有参照)。"""
    s = SessionLocal()
    try:
        s.query(Run).filter(Run.id == run_id).update(
            {Run.last_progress_at: _now_str()}, synchronize_session=False)
        s.commit()
    except Exception as e:
        logger.warning("run 进度时间写入失败: %s", e, extra={"run_id": run_id})
    finally:
        s.close()


def _bump_progress(run_id: int) -> None:
    """进度自增(原子 UPDATE progress = progress + 1,避免并发读-改-写竞争)。"""
    s = SessionLocal()
    s.query(Run).filter(Run.id == run_id).update(
        {Run.progress: Run.progress + 1,
         Run.last_heartbeat_at: _now_str(),
         Run.last_progress_at: _now_str()},
        synchronize_session=False)
    s.commit()
    s.close()
