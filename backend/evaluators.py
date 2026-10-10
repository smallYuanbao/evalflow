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
REJECT_MARKERS = ["不清楚", "不知道", "无法回答", "无法提供", "没有相关", "没有证据", "无法给出"]


def rejected(output: str) -> float:
    """机械判断回答是否为「拒答」。命中任一拒答词 → 1.0,否则 0.0(确定性,不碰 LLM)。"""
    return 1.0 if any(m in output for m in REJECT_MARKERS) else 0.0


def recall(expected_output: str, retrieved_context: str) -> float:
    """机械匹配:ground truth 要点命中率。expected_output 用 / 切要点,判断子串是否出现在 context。"""
    points = [p.strip() for p in expected_output.split("/") if p.strip()]
    if not points:
        return 0.0
    hits = sum(1 for p in points if p in retrieved_context)
    return round(hits / len(points), 4)


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
    return {"score": round(sum(scores) / len(scores), 4), "reason": reason}


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
