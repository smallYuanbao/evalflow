import json
import time

from backend.db import SessionLocal
from backend.evaluators import faithfulness, recall, rejected
from backend.models import DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline

ABSENT_BUCKET = "库外"  # 库外题:知识库里没有答案,正确行为是拒答


def execute_run(run_id: int) -> None:
    s = SessionLocal()
    run = s.get(Run, run_id)
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == run.dataset_id).all()
    try:
        for it in items:
            t0 = time.time()
            out = run_pipeline(it.input)
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
                # 库外题:只评「拒答」(正确行为是不答),不评 recall/faithfulness
                s.add(Score(trace_id=tr.id, name="rejection",
                            value=rejected(out["output"])))
            else:
                # recall 机械匹配(确定性)
                s.add(Score(trace_id=tr.id, name="recall",
                            value=recall(it.expected_output, out["retrieved_context"])))
                # faithfulness LLM judge(可能挂,挂则 NULL)
                f = faithfulness(out["output"], out["retrieved_context"])
                if f is None:
                    s.add(Score(trace_id=tr.id, name="faithfulness", value=None, comment="judge 失败"))
                else:
                    s.add(Score(trace_id=tr.id, name="faithfulness", value=f["score"], comment=f["reason"]))
        run.status = "done"
        s.commit()
    except Exception:
        s.rollback()
        run = s.get(Run, run_id)
        run.status = "failed"
        s.commit()
    finally:
        s.close()
