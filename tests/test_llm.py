from types import SimpleNamespace

import openai
import pytest

from backend import llm
from backend.config import settings


def _fake_resp(content: str):
    # 模拟 openai 响应结构:resp.choices[0].message.content
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


# —— Ch02 已有 ——

def test_chat_json_parses(monkeypatch):
    monkeypatch.setattr(
        llm._client.chat.completions, "create",
        lambda **kw: _fake_resp('{"score": 0.8, "reason": "ok"}'),
    )
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"score": 0.8, "reason": "ok"}


def test_chat_json_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(
        llm._client.chat.completions, "create",
        lambda **kw: _fake_resp("不是 json"),
    )
    assert llm.chat_json([{"role": "user", "content": "x"}]) is None


# —— Ch11 重试 + 熔断 ——

def test_retry_then_success(monkeypatch):
    llm._circuit._reset()
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise openai.APITimeoutError("超时")
        return _fake_resp('{"score": 0.8, "reason": "ok"}')

    monkeypatch.setattr(llm._client.chat.completions, "create", fake_create)
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"score": 0.8, "reason": "ok"}
    assert calls["n"] == 2  # 第一次超时,重试成功


def test_retry_exhausted_raises(monkeypatch):
    llm._circuit._reset()
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        raise openai.APITimeoutError("超时")

    monkeypatch.setattr(llm._client.chat.completions, "create", fake_create)
    with pytest.raises(openai.APITimeoutError):
        llm.chat([{"role": "user", "content": "x"}])
    assert calls["n"] == settings.chat_retries + 1  # 重试耗尽:共 4 次尝试


def test_non_retryable_not_retried(monkeypatch):
    llm._circuit._reset()
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        raise ValueError("4xx 参数错(非可重试)")

    monkeypatch.setattr(llm._client.chat.completions, "create", fake_create)
    with pytest.raises(ValueError):
        llm.chat([{"role": "user", "content": "x"}])
    assert calls["n"] == 1  # 非可重试,不重试


def test_circuit_open_fast_fails(monkeypatch):
    llm._circuit._reset()
    llm._circuit._state = "open"
    llm._circuit._opened_at = 1000.0
    monkeypatch.setattr(llm.time, "monotonic", lambda: 1000.0)  # 时钟不动,冷却未结束
    calls = {"n": 0}

    def fake_create(**kw):
        calls["n"] += 1
        return _fake_resp("hi")

    monkeypatch.setattr(llm._client.chat.completions, "create", fake_create)
    with pytest.raises(llm.CircuitOpenError):
        llm.chat([{"role": "user", "content": "x"}])
    assert calls["n"] == 0  # 熔断打开,根本不调 LLM


def test_circuit_half_open_recovers(monkeypatch):
    llm._circuit._reset()
    llm._circuit._state = "open"
    llm._circuit._opened_at = 1000.0
    monkeypatch.setattr(llm.time, "monotonic",
                        lambda: 1000.0 + llm._circuit.cooldown_seconds + 1)
    monkeypatch.setattr(llm._client.chat.completions, "create", lambda **kw: _fake_resp("hi"))
    assert llm.chat([{"role": "user", "content": "x"}]) == "hi"
    assert llm._circuit._state == "closed"  # 探测成功,熔断关闭
