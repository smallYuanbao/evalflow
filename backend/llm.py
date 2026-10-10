import json
import random
import threading
import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from backend.config import settings

_client = OpenAI(api_key=settings.chat_api_key, base_url=settings.chat_base_url,
                 timeout=settings.chat_timeout)

# 可重试异常:网络层(超时/连接)+ 服务端瞬时(429 限流 / 5xx)。
# 4xx(鉴权/参数错)不重试——重试一万次也没用。
_RETRYABLE = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)


class CircuitOpenError(Exception):
    """熔断打开:LLM 连续失败过多,短期内直接快速失败,不再真实调用。"""


class CircuitBreaker:
    """熔断器状态机:closed → open(连续失败达阈值)→ half-open(冷却后探测)→ closed。

    模块级单例,所有 LLM 调用共享(只有一个 chat 模型/endpoint)。
    """

    def __init__(self, failure_threshold: int, cooldown_seconds: float):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._state = "closed"
        self._consecutive_failures = 0
        self._opened_at = 0.0

    def _reset(self) -> None:
        """测试用:回到初始 closed 状态。"""
        with self._lock:
            self._state = "closed"
            self._consecutive_failures = 0
            self._opened_at = 0.0

    def before_call(self) -> None:
        with self._lock:
            if self._state == "open":
                if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                    self._state = "half-open"  # 冷却结束,放一个探测请求
                else:
                    raise CircuitOpenError("熔断打开中,短期快速失败,不再调用 LLM")

    def on_success(self) -> None:
        with self._lock:
            self._state = "closed"
            self._consecutive_failures = 0

    def on_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == "half-open" or self._consecutive_failures >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()


_circuit = CircuitBreaker(settings.chat_circuit_failures, settings.chat_circuit_cooldown)


def _backoff(attempt: int) -> float:
    """指数退避 + 抖动:base * 2^attempt,叠加 [0, base) 随机,错峰避免并发惊群。"""
    return settings.chat_retry_base * (2 ** attempt) + random.uniform(0, settings.chat_retry_base)


def _create_with_retry(**kwargs):
    """统一 LLM 调用出口:过熔断闸门 + 可重试错误的指数退避重试。"""
    last_exc = None
    for attempt in range(settings.chat_retries + 1):
        _circuit.before_call()  # open 直接抛 CircuitOpenError(快速失败,不打 LLM)
        try:
            r = _client.chat.completions.create(**kwargs)
            _circuit.on_success()
            return r
        except _RETRYABLE as e:
            last_exc = e
            _circuit.on_failure()
            if attempt < settings.chat_retries:
                time.sleep(_backoff(attempt))
        except Exception:
            # 非可重试(4xx 等):服务是通的,不算故障,重置熔断后直接抛
            _circuit.on_success()
            raise
    raise last_exc


def chat(messages: list[dict], temperature: float = 0.0) -> str:
    r = _create_with_retry(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
    )
    return r.choices[0].message.content or ""


def chat_json(messages: list[dict], temperature: float = 0.0) -> dict | None:
    """JSON mode 强制输出 JSON;解析失败返回 None(调用方按失败处理)。"""
    r = _create_with_retry(
        model=settings.chat_model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = r.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None
