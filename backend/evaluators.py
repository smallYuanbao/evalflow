from backend import llm
from backend.prompts import FAITHFULNESS_PROMPT

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


def faithfulness(output: str, retrieved_context: str) -> dict | None:
    """LLM judge,温度 0。失败返回 None(记 NULL 不记 0)。"""
    prompt = FAITHFULNESS_PROMPT.format(context=retrieved_context, answer=output)
    try:
        raw = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0)
        if raw is None or "score" not in raw:
            return None
        score = float(raw["score"])
        score = min(max(score, 0.0), 1.0)
        return {"score": round(score, 4), "reason": str(raw.get("reason", ""))}
    except Exception:
        return None
