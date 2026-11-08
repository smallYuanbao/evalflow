from backend import llm
from backend.config import settings
from backend.prompts import (
    ANSWER_CORRECTNESS_PROMPT,
    ANSWER_RELEVANCE_PROMPT,
    CONTEXT_PRECISION_PROMPT,
    CONTEXT_RECALL_PROMPT,
    FAITHFULNESS_PROMPT,
    REJECTION_PROMPT,
)

# 拒答信号词:命中任一即判定为「拒答」(库外题的正确行为)
REJECT_MARKERS = [
    # 说「不知道 / 没有证据」
    "不清楚", "不知道", "无法回答", "无法提供", "没有相关", "没有证据", "无法给出",
    # 说「超出范围 / 只答某类」(Ch27:接真实系统 baby-ai 时补的。它拒答时说「只能回答育儿相关
    # 问题」「不在我的专业范围内」,原词表一个都匹配不上 → 库外题被误判成「没拒答」。)
    #
    # 注意用词要**宽**:第一版写的是「我只能回答」,结果下一次 run 它说成「只能回答育儿相关问题」
    # (少了个「我」),照样漏。同一个模型换个 run 措辞就会漂——词表不能贴某一次的输出写。
    "只能回答", "不在我的专业", "不是我的专业", "不属于我能回答", "超出我的专业", "超出我的能力范围", "帮不上忙",
]


def rejected(output: str) -> float:
    """机械判断回答是否为「拒答」。命中任一拒答词 → 1.0,否则 0.0(确定性,不碰 LLM)。

    **这是启发式,不是判定**:词表覆盖不到的说法会漏判;反过来,「嘴上说超出范围、
    实际仍作答」又会被误判成拒答。它是双信号里的**快速信号**,不单独下结论——
    最终判定见 {@link rejection_dual}。
    """
    return 1.0 if any(m in output for m in REJECT_MARKERS) else 0.0


def rejection_judge(question: str, output: str) -> dict | None:
    """LLM 裁判:回答是否真的拒答(看有没有实质作答,而不是只看措辞)。"""
    return _judge(REJECTION_PROMPT.format(question=question, answer=output))


def rejection_dual(question: str, output: str) -> tuple[float, str]:
    """拒答双信号:词表 + LLM judge,judge 主判、词表兜底。

    判定规则:
      · judge 成功 → 以 judge 为准(能识别「口头拒答但实际作答」和「没命中文词的真拒答」);
      · 两信号不一致 → 仍以 judge 为准,并把分歧写进 comment,方便回看词表是否该扩;
      · judge 失败(LLM 不可用/解析失败) → 回退词表,保证评测不因裁判故障中断。

    Returns:
        (value, comment):value 1.0=拒答,0.0=未拒答;comment 记录两信号与分歧原因。
    """
    marker = rejected(output)
    judged = rejection_judge(question, output)
    if judged is None:
        return marker, f"judge 失败,回退词表判定(词表={marker})"

    value = 1.0 if judged["score"] >= 0.5 else 0.0
    reason = judged.get("reason", "")
    if value == marker:
        return value, f"双信号一致(词表={marker}, judge={value}):{reason}"
    return value, f"双信号不一致(词表={marker}, judge={value}),以 judge 为准:{reason}"


def _points(expected_output: str) -> list[str]:
    return [p.strip() for p in expected_output.split("/") if p.strip()]


def _has_context(retrieved_context: str) -> bool:
    return bool(retrieved_context.strip()) and retrieved_context.strip() != "(无证据)"


def point_hit(point: str, text: str) -> bool:
    """一个要点命中文本；`a|b` 表示任一说法都算。

    ecom 的要点来自 Ch02 的正则/同义词（如「不可叠加|不能叠加」），
    EvalFlow 侧做向后兼容的任选语义；不含 `|` 的旧数据行为不变。
    """
    return any(alt.strip() and alt.strip() in text for alt in point.split("|"))


def recall(expected_output: str, retrieved_context: str) -> float | None:
    """机械匹配:ground truth 要点命中率。

    没有检索上下文（B/C/E 出口）时返回 None，不记 0——
    「没有检索」和「检索了但没命中」是两件事。
    """
    points = _points(expected_output)
    if not points:
        return 0.0
    if not _has_context(retrieved_context):
        return None
    hits = sum(1 for p in points if point_hit(p, retrieved_context))
    return round(hits / len(points), 4)


def hit_at_k(expected_output: str, hits: list[dict]) -> float | None:
    """检索命中率@k:top-k 里是否命中任一相关 chunk(0/1)。

    没有 hits（非知识出口）时返回 None，不记 0。
    """
    points = _points(expected_output)
    if not points:
        return 0.0
    if not hits:
        return None
    return 1.0 if any(
        any(point_hit(p, h["text"]) for p in points) for h in hits
    ) else 0.0


def mrr(expected_output: str, hits: list[dict]) -> float | None:
    """MRR 倒数排名:1 / 首个相关 chunk 的排名；没有 hits 时返回 None。"""
    points = _points(expected_output)
    if not points:
        return 0.0
    if not hits:
        return None
    for i, h in enumerate(hits):
        if any(point_hit(p, h["text"]) for p in points):
            return round(1.0 / (i + 1), 4)
    return 0.0


def _judge(prompt: str) -> dict | None:
    """LLM judge:采样 judge_samples 次取均值(更稳),全部失败返回 None(记 NULL 不记 0)。"""
    scores: list[float] = []
    reason = ""
    for _ in range(max(1, settings.judge_samples)):
        try:
            raw = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0)
            if raw is None or "score" not in raw:
                continue
            score = min(max(float(raw["score"]), 0.0), 1.0)
            scores.append(score)
            if not reason:
                reason = str(raw.get("reason", ""))
        except Exception:
            continue
    if not scores:
        return None
    mean = sum(scores) / len(scores)
    # 采样方差(Ch20):识别「不稳定 judge」;单样本无法定义方差,记 None
    variance = sum((s - mean) ** 2 for s in scores) / len(scores) if len(scores) > 1 else None
    return {
        "score": round(mean, 4),
        "variance": round(variance, 6) if variance is not None else None,
        "reason": reason,
    }


def faithfulness(output: str, retrieved_context: str) -> dict | None:
    """生成阶段:回答是否忠于证据、不编造。"""
    return _judge(FAITHFULNESS_PROMPT.format(context=retrieved_context, answer=output))


def context_precision(question: str, retrieved_context: str) -> dict | None:
    """检索阶段:证据里相关有用的占比(噪声少)。"""
    return _judge(CONTEXT_PRECISION_PROMPT.format(question=question, context=retrieved_context))


def context_recall(question: str, expected_output: str, retrieved_context: str) -> dict | None:
    """检索阶段:标准答案要点被证据覆盖的比例(漏检少)。"""
    return _judge(CONTEXT_RECALL_PROMPT.format(question=question, expected=expected_output, context=retrieved_context))


def answer_relevance(question: str, output: str) -> dict | None:
    """生成阶段:回答是否切题、不跑题。"""
    return _judge(ANSWER_RELEVANCE_PROMPT.format(question=question, answer=output))


def answer_correctness(question: str, expected_output: str, output: str) -> dict | None:
    """生成阶段:回答与标准答案要点的语义一致度。"""
    return _judge(ANSWER_CORRECTNESS_PROMPT.format(question=question, expected=expected_output, answer=output))
