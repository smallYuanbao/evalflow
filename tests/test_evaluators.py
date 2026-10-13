from backend import evaluators


def test_recall_full_hit():
    ctx = "宝宝发烧38度以上可物理降温;超过39度要就医;退烧用药需遵医嘱。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == 1.0


def test_recall_partial_hit():
    ctx = "宝宝发烧可物理降温。"
    assert evaluators.recall("物理降温/就医/用药", ctx) == round(1 / 3, 4)


def test_hit_at_k():
    hits = [{"text": "物理降温", "score": 0.9}, {"text": "睡眠", "score": 0.8}]
    assert evaluators.hit_at_k("物理降温/就医", hits) == 1.0   # 首个命中
    assert evaluators.hit_at_k("就医/用药", hits) == 0.0         # 全没命中
    assert evaluators.hit_at_k("", hits) == 0.0                  # 无要点


def test_mrr():
    hits = [{"text": "睡眠", "score": 0.9}, {"text": "就医", "score": 0.8}]
    assert evaluators.mrr("物理降温/就医", hits) == 0.5   # 就医排第 2
    assert evaluators.mrr("物理降温/用药", hits) == 0.0    # 全没相关
    assert evaluators.mrr("睡眠/就医", hits) == 1.0        # 睡眠排第 1


def test_rejected_hits_marker():
    assert evaluators.rejected("抱歉，目前没有相关证据，我不清楚怎么处理。") == 1.0


def test_rejected_no_marker():
    assert evaluators.rejected("宝宝发烧可以物理降温。") == 0.0


def test_rejected_recognizes_scope_refusal():
    """Ch27:接真实系统 baby-ai 时补的措辞——它拒答时说「超出专业范围」而不是「不知道」。

    全部用 baby-ai 的**真实回答原文**(含 emoji / markdown),不用理想化句子。
    """
    # Run 6 / 8 的说法
    car = ("🏷️ **先给结论**：\n抱歉，我只能回答育儿相关问题哦～ 换汽车轮胎属于汽车维修领域，"
           "不在我的专业范围内，我不能给您不专业的建议。")
    travel = "抱歉，我只能回答育儿相关问题哦～🐻\n\n不过如果您是想**带宝宝去北京玩**，那我可以帮上忙——比如："
    assert evaluators.rejected(car) == 1.0
    assert evaluators.rejected(travel) == 1.0

    # Run 9 换了说法:少了个「我」,还说成「不属于我能回答的范围」——
    # 第一版词表写死「我只能回答」,这条就漏了。用例留着防这种措辞漂移。
    run9_travel = ("🏷️ **先给结论**：抱歉，我是育儿助手小熊🐻，只能回答育儿相关问题哦～"
                   "「北京旅游景点推荐」不属于我能回答的范围，我的建议也会误导你。")
    assert evaluators.rejected(run9_travel) == 1.0


def test_judge_returns_score(monkeypatch):
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": 0.9, "reason": "ok"})
    assert evaluators.faithfulness("答", "证") == {"score": 0.9, "variance": None, "reason": "ok"}


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


def test_judge_samples_average(monkeypatch):
    # judge_samples=3 时采样 3 次取均值(Ch11 校准)
    monkeypatch.setattr(evaluators.settings, "judge_samples", 3)
    scores = iter([0.6, 0.9, 1.0])
    monkeypatch.setattr(evaluators.llm, "chat_json",
                        lambda *a, **kw: {"score": next(scores), "reason": "ok"})
    r = evaluators.faithfulness("a", "c")
    assert r["score"] == round((0.6 + 0.9 + 1.0) / 3, 4)


def test_judge_variance(monkeypatch):
    # 多采样时算方差;单采样方差为 None(Ch20)
    monkeypatch.setattr(evaluators.settings, "judge_samples", 3)
    scores = iter([0.6, 0.9, 1.0])
    monkeypatch.setattr(evaluators.llm, "chat_json",
                        lambda *a, **kw: {"score": next(scores), "reason": "ok"})
    r = evaluators.faithfulness("a", "c")
    mean = (0.6 + 0.9 + 1.0) / 3
    expected_var = ((0.6 - mean) ** 2 + (0.9 - mean) ** 2 + (1.0 - mean) ** 2) / 3
    assert abs(r["variance"] - expected_var) < 1e-6

    monkeypatch.setattr(evaluators.settings, "judge_samples", 1)
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: {"score": 0.8, "reason": "ok"})
    assert evaluators.faithfulness("a", "c")["variance"] is None


def test_judge_samples_skip_failures(monkeypatch):
    # 中间一次采样失败,用成功的取均值
    monkeypatch.setattr(evaluators.settings, "judge_samples", 3)
    results = iter([{"score": 0.6}, None, {"score": 1.0}])  # 第二次失败
    monkeypatch.setattr(evaluators.llm, "chat_json", lambda *a, **kw: next(results))
    r = evaluators.faithfulness("a", "c")
    assert r["score"] == round((0.6 + 1.0) / 2, 4)
