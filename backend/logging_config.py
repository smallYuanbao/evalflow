"""结构化日志(Ch13):每行一条 JSON,关键字段独立可检索。

只配置 `backend` 命名空间的 logger,不碰 uvicorn/celery 自带的 logger,
避免重复输出 / 格式打架。API 与 worker 两个进程分别在入口调 setup_logging()。
"""
import json
import logging
from datetime import datetime, timezone

# 通过 extra 传入的关键字段:日志里单独成列,方便按字段检索/聚合
_CONTEXT_FIELDS = ("run_id", "trace_id", "latency_ms", "duration_ms", "attempt")


class JsonFormatter(logging.Formatter):
    """把一条日志记录格式化为单行 JSON:基础字段 + extra 上下文字段 + 异常堆栈。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in _CONTEXT_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """配置 `backend` logger 走 JSON 输出(幂等,进程内只生效一次)。"""
    logger = logging.getLogger("backend")
    if logger.handlers:  # 已配置过(如 uvicorn reload / 重复调用)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 不冒泡到 root,避免与 uvicorn/celery 的 root handler 重复打印
