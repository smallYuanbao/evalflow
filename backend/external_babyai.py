"""评测外部系统:baby-ai(Ch26)。

把 EvalFlow 的被测系统从「自己的 toy pipeline」换成真实 RAG 应用 baby-ai,
形成「开发 → 评测 → 优化 → 再评测」的闭环。

两件事:
  · run_pipeline_babyai —— 走它的 /api/chat,组装成 EvalFlow 要的 {output, retrieved_context, hits};
  · fetch_meta         —— 走它的 /api/meta,拿到**对方系统的状态**,记进 run 快照。

为什么必须有 fetch_meta:可复现性有一半在对方系统里。只记自己这边(知识库/prompt/模型),
「这次比上次好」就说不清是「改了检索」还是「对方知识库/模型变了」——那只是一句话,不是结论。
"""
import logging
import threading
import time
from uuid import uuid4

import requests

from backend.config import settings

logger = logging.getLogger(__name__)

# —— 自我限流 ——
# baby-ai 的 /api/chat 有 10/min 的限制(那是它对**所有调用方**的保护)。
# 评测会并发打请求,不自我限速就会吃 429、整个 run 直接失败(实测踩过:20 条并发 2 → 进度 7 挂掉)。
# 所以适配器的职责之一,是**尊重被测系统的限流**——这是「评测别人」应有的分寸。
_throttle_lock = threading.Lock()
_recent_calls: list[float] = []


def _throttle() -> None:
    """确保最近一分钟发出的请求数不超过 babyai_max_rpm;超了就等到窗口滑过去。"""
    limit = max(1, settings.babyai_max_rpm)
    with _throttle_lock:
        now = time.monotonic()
        _recent_calls[:] = [t for t in _recent_calls if now - t < 60]
        if len(_recent_calls) >= limit:
            wait = 60 - (now - _recent_calls[0]) + 0.3
            logger.info("自我限流:等待 %.1fs(目标 %d 次/分)", wait, limit)
            time.sleep(wait)
            now = time.monotonic()
            _recent_calls[:] = [t for t in _recent_calls if now - t < 60]
        _recent_calls.append(now)


def run_pipeline_babyai(question: str, top_k: int = 2, retrieval: str = "hybrid") -> dict:
    """调 baby-ai 的 /api/chat,把它的回答与检索证据组装成 EvalFlow 的 pipeline 输出。

    top_k / retrieval 在这里**不生效**——baby-ai 自己决定检索策略(它内部有混合检索 +
    精排 + 查询改写)。传参只是保持 run_pipeline 的签名一致。这是「端到端评测」的含义:
    被测系统的内部策略是黑盒,我们只量它最终给出的质量。
    """
    # 每次全新 session_id + 不带 history:避免题与题之间通过多轮记忆互相污染
    payload = {"message": question, "session_id": f"eval-{uuid4()}"}
    # 兜底重试:自我限流后仍偶发 429(比如别的调用方也在打),退避重试几次
    for attempt in range(3):
        _throttle()
        r = requests.post(f"{settings.babyai_base_url}/api/chat", json=payload,
                          timeout=settings.babyai_timeout)
        if r.status_code == 429 and attempt < 2:
            logger.warning("被测系统返回 429,退避重试(%d/3)", attempt + 1)
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    d = r.json()

    refs = d.get("references") or []
    context = "\n".join(x["text"] for x in refs) or "(无证据)"
    return {
        "output": d["answer"],
        "retrieved_context": context,
        # baby-ai 的 Reference 只暴露 {id, text},没有分数。
        # hit@k / MRR 只用 text + 顺序,不受影响;score 只是前端「融合分」的展示位,填 0 占位。
        "hits": [{"text": x["text"], "score": 0.0} for x in refs],
    }


def fetch_meta() -> dict | None:
    """取被测系统的状态(版本/模型/检索配置/知识库规模)。

    拿不到返回 None——**调用方必须显式标记「未知」,不能静默记空**:
    静默记空会让人误信「这次结果可与历史对比」,比不记更危险。
    """
    try:
        r = requests.get(f"{settings.babyai_base_url}/api/meta", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.warning("取 baby-ai meta 失败: %s", e)
        return None
