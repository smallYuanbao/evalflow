from backend import evaluators


def test_recall_full_hit():
    ctx = "宝宝发烧38度以上可物理降温;超过39度要就医;退烧用药需遵医嘱。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == 1.0


def test_recall_partial_hit():
    ctx = "宝宝发烧可物理降温。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == round(1 / 3, 4)


def test_rejected_hits_marker():
    assert evaluators.rejected("抱歉，目前没有相关证据，我不清楚怎么处理。") == 1.0


def test_rejected_no_marker():
    assert evaluators.rejected("宝宝发烧可以物理降温。") == 0.0


def test_judge_returns_score(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": 0.9, "reason": "ok"})
    assert evaluators.faithfulness("答", "证") == {"score": 0.9, "reason": "ok"}


def test_judge_clamps_score(monkeypatch):
    # 模型给了超范围分数 → 夹逼到 [0,1]
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": 2.5, "reason": "x"})
    assert evaluators.answer_relevance("q", "a")["score"] == 1.0
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": -1.0, "reason": "x"})
    assert evaluators.answer_relevance("q", "a")["score"] == 0.0


def test_judge_returns_none_on_missing_score(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"reason": "没有 score"})
    assert evaluators.context_precision("q", "c") is None


def test_judge_returns_none_on_exception(monkeypatch):
    # judge 超时/抛异常 → 记 NULL(不算 run 失败)
    def _boom(*a, **kw):
        raise Exception("timeout")

    monkeypatch.setattr(evaluators.llm, "chat_json", _boom)
    assert evaluators.context_recall("q", "e", "c") is None


def test_all_five_judges(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": 0.5, "reason": "ok"})
    assert evaluators.faithfulness("a", "c")["score"] == 0.5
    assert evaluators.context_precision("q", "c")["score"] == 0.5
    assert evaluators.context_recall("q", "e", "c")["score"] == 0.5
    assert evaluators.answer_relevance("q", "a")["score"] == 0.5
    assert evaluators.answer_correctness("q", "e", "a")["score"] == 0.5
