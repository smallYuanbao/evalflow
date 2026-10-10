"""内存滑动窗口限流(Ch12 防刷):只挡「发起评测」这个烧钱操作。

单进程内存即可——create_run 只在 FastAPI 进程处理,不涉及 Celery worker。
分布式限流(Redis)是后面章节的事。
"""
import time
from collections import deque
from threading import Lock

from backend.config import settings


class SlidingWindowLimiter:
    """窗口内最多 max_requests 次,超限 allow() 返回 False(调用方返回 429)。"""

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = Lock()
        self._hits = deque()  # 记录窗口内每次放行的时间戳

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            # 滑出窗口的旧时间戳作废
            while self._hits and now - self._hits[0] >= self.window_seconds:
                self._hits.popleft()
            if len(self._hits) >= self.max_requests:
                return False
            self._hits.append(now)
            return True

    def _reset(self) -> None:
        """测试用:清空计数。"""
        with self._lock:
            self._hits.clear()


run_limiter = SlidingWindowLimiter(settings.rate_limit_runs_per_minute)
