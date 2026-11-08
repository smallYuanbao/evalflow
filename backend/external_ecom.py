"""评测外部系统：ecom-agent（Ch07）。

ecom 暴露两个接口：

- `POST /api/eval/chat` → answer / references / hits / signals（非流式）
- `GET  /api/meta`      → kb_version / 模型 / prompt 版本（run 快照用）

和 baby-ai 的差异：

| 点 | baby-ai | ecom |
|---|---|---|
| 接口 | `/api/chat` JSON | `/api/eval/chat` JSON |
| 证据 | references | references + 完整 top-k hits |
| 重试 | 429 退避 | 429/5xx/超时退避；4xx 不重试 |

**top_k / retrieval 不生效**：ecom 内部自己决定检索策略，评测只量最终质量。
"""
import logging
import threading
import time

import requests

from backend.config import settings

logger = logging.getLogger(__name__)

_throttle_lock = threading.Lock()
_recent_calls: list[float] = []


def _throttle() -> None:
    limit = max(1, settings.ecom_max_rpm)
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


def _post(payload: dict) -> dict:
    """带重试的 POST：429 / 5xx / 超时退避；4xx 立即失败（样本错误）。"""
    url = f"{settings.ecom_base_url}/api/eval/chat"
    last_error: Exception | None = None
    for attempt in range(3):
        _throttle()
        try:
            response = requests.post(url, json=payload, timeout=settings.ecom_timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2**attempt)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            last_error = RuntimeError(f"ecom {response.status_code}")
            if attempt == 2:
                response.raise_for_status()
            time.sleep(2**attempt)
            continue

        response.raise_for_status()
        return response.json()
    raise last_error or RuntimeError("ecom 调用失败")


def run_pipeline_ecom(question: str, top_k: int = 2, retrieval: str = "hybrid") -> dict:
    data = _post({"message": question})
    references = data.get("references") or []
    context = "\n".join(str(item.get("text") or "") for item in references) or "(无证据)"
    hits = [
        {
            "text": str(item.get("text") or ""),
            "score": item.get("score") if item.get("score") is not None else 0.0,
        }
        for item in (data.get("hits") or [])
    ]
    return {"output": str(data.get("answer") or ""), "retrieved_context": context, "hits": hits}


def fetch_meta() -> dict | None:
    """取被测系统状态；拿不到返回 None，由快照显式标 meta_error。"""
    try:
        response = requests.get(f"{settings.ecom_base_url}/api/meta", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:                       # noqa: BLE001
        logger.warning("取 ecom meta 失败: %s", exc)
        return None
