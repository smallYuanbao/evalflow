from backend import evaluators


def test_recall_full_hit():
    ctx = "宝宝发烧38度以上可物理降温;超过39度要就医;退烧用药需遵医嘱。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == 1.0


def test_recall_partial_hit():
    ctx = "宝宝发烧可物理降温。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == round(1 / 3, 4)


def test_faithfulness_failure_returns_none(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: None)
    assert evaluators.faithfulness("答", "证") is None


def test_rejected_hits_marker():
    assert evaluators.rejected("抱歉，目前没有相关证据，我不清楚怎么处理。") == 1.0


def test_rejected_no_marker():
    assert evaluators.rejected("宝宝发烧可以物理降温。") == 0.0
