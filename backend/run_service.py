import json
import time

from backend.db import SessionLocal
from backend.evaluators import (
    answer_correctness,
    answer_relevance,
    context_precision,
    context_recall,
    faithfulness,
    recall,
    rejected,
)
from backend.models import DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline

ABSENT_BUCKET = "库外"  # 库外题:知识库里没有答案,正确行为是拒答


def _config_top_k(config_str: str) -> int:
    """从 config 快照取 top_k(检索命中数),缺省/解析失败回退默认 2(兼容老 run 的空 config)。"""
    try:
        return int(json.loads(config_str or "{}").get("top_k", 2))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2


def execute_run(run_id: int) -> None:
    s = SessionLocal()
    run = s.get(Run, run_id)
    top_k = _config_top_k(run.config)
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == run.dataset_id).all()
    try:
        for it in items:
            t0 = time.time()
            out = run_pipeline(it.input, top_k)
            latency_ms = int((time.time() - t0) * 1000)
            hits = [{"text": h["text"], "score": h["score"], "rank": i + 1}
                    for i, h in enumerate(out["hits"])]
            tr = Trace(run_id=run.id, dataset_item_id=it.id,
                       input=it.input, output=out["output"],
                       retrieved_context=out["retrieved_context"],
                       retrieval_hits=json.dumps(hits, ensure_ascii=False),
                       latency_ms=latency_ms)
            s.add(tr)
            s.flush()
            if it.bucket == ABSENT_BUCKET:
                # 库外题:只评「拒答」(正确行为是不答)
                s.add(Score(trace_id=tr.id, name="rejection", value=rejected(out["output"])))
            else:
                # recall 机械基线(确定性,0 次 LLM)
                s.add(Score(trace_id=tr.id, name="recall",
                            value=recall(it.expected_output, out["retrieved_context"])))
                # 5 个 LLM judge:统一「judge 挂记 NULL 不记 0」
                judges = [
                    ("context_precision", context_precision(it.input, out["retrieved_context"])),
                    ("context_recall", context_recall(it.input, it.expected_output, out["retrieved_context"])),
                    ("faithfulness", faithfulness(out["output"], out["retrieved_context"])),
                    ("answer_relevance", answer_relevance(it.input, out["output"])),
                    ("answer_correctness", answer_correctness(it.input, it.expected_output, out["output"])),
                ]
                for name, r in judges:
                    if r is None:
                        s.add(Score(trace_id=tr.id, name=name, value=None, comment="judge 失败"))
                    else:
                        s.add(Score(trace_id=tr.id, name=name, value=r["score"], comment=r["reason"]))
        run.status = "done"
        s.commit()
    except Exception:
        s.rollback()
        run = s.get(Run, run_id)
        run.status = "failed"
        s.commit()
    finally:
        s.close()
