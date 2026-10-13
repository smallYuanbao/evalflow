from backend import llm
from backend.config import settings
from backend.prompts import (
    ANSWER_CORRECTNESS_PROMPT,
    ANSWER_RELEVANCE_PROMPT,
    CONTEXT_PRECISION_PROMPT,
    CONTEXT_RECALL_PROMPT,
    FAITHFULNESS_PROMPT,
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

    **这是启发式,不是判定**:词表覆盖不到的说法一律算「没拒答」(漏判)。
    代价换来的是确定性 + 零成本(不烧 LLM),作为「库外题正确行为」的机械基线够用。
    要更准只能上 LLM judge——但那样就失去了「机械基线」的意义,且引入方差。
    评估新被测系统时,先看它实际的拒答措辞,按需扩这个词表。
    """
    return 1.0 if any(m in output for m in REJECT_MARKERS) else 0.0


def recall(expected_output: str, retrieved_context: str) -> float:
    """机械匹配:ground truth 要点命中率。expected_output 用 / 切要点,判断子串是否出现在 context。"""
    points = [p.strip() for p in expected_output.split("/") if p.strip()]
    if not points:
        return 0.0
    hits = sum(1 for p in points if p in retrieved_context)
    return round(hits / len(points), 4)


def _points(expected_output: str) -> list[str]:
    return [p.strip() for p in expected_output.split("/") if p.strip()]


def hit_at_k(expected_output: str, hits: list[dict]) -> float:
    """检索命中率@k(Ch20):top-k 里是否命中任一相关 chunk(0/1)。

    相关 = chunk 文本含任一要点(与 recall 同源推导,零新增标注)。
    """
    points = _points(expected_output)
    if not points:
        return 0.0
    return 1.0 if any(any(p in h["text"] for p in points) for h in hits) else 0.0


def mrr(expected_output: str, hits: list[dict]) -> float:
    """MRR 倒数排名(Ch20):1 / 首个相关 chunk 的排名;没有相关命中则 0。"""
    points = _points(expected_output)
    if not points:
        return 0.0
    for i, h in enumerate(hits):
        if any(p in h["text"] for p in points):
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
