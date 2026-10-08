from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Score, Trace
from backend.pipeline import run_pipeline


def seed() -> None:
    init_db()
    s = SessionLocal()
    ds = Dataset(name="育儿-常见病", description="示例评测集")
    s.add(ds)
    s.flush()

    items = [
        DatasetItem(dataset_id=ds.id, input="宝宝发烧38度怎么办",
                    expected_output="物理降温/就医指征/用药", bucket="护理"),
        DatasetItem(dataset_id=ds.id, input="6个月能加辅食吗",
                    expected_output="月龄标准/首选食物", bucket="喂养"),
        DatasetItem(dataset_id=ds.id, input="宝宝晚上总醒怎么回事",
                    expected_output="睡眠倒退/出牙/环境", bucket="睡眠"),
    ]
    s.add_all(items)
    s.flush()

    run = Run(dataset_id=ds.id, status="done", config='{"model": "mock"}')
    s.add(run)
    s.flush()

    for i, it in enumerate(items[:2]):
        out = run_pipeline(it.input)
        tr = Trace(run_id=run.id, dataset_item_id=it.id,
                   input=it.input, output=out["output"],
                   retrieved_context=out["retrieved_context"], latency_ms=100)
        s.add(tr)
        s.flush()
        s.add(Score(trace_id=tr.id, name="faithfulness", value=4.5, comment="mock"))
        if i == 0:
            # 验证 scores.value 可空:这条 judge 挂了,记 NULL 不记 0
            s.add(Score(trace_id=tr.id, name="recall", value=None, comment="judge 未评上"))

    s.commit()
    s.close()


if __name__ == "__main__":
    seed()
