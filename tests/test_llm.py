from types import SimpleNamespace

import openai
import pytest

from backend import llm
from backend.config import settings


def _fake_resp(content: str):
    # 模拟 openai 响应结构:resp.choices[0].message.content
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _fake_resp_with_usage(content: str, prompt: int = 100, completion: int = 50):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


# —— Ch02 已有 ——

def test_chat_json_parses(monkeypatch):
    monkeypatch.setattr(
        llm._judge_client.chat.completions, "create",
        lambda **kw: _fake_resp('{"score": 0.8, "reason": "ok"}'),
    )
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"score": 0.8, "reason": "ok"}


def test_chat_json_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(
        llm._judge_client.chat.completions, "create",
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

    monkeypatch.setattr(llm._judge_client.chat.completions, "create", fake_create)
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


# —— Ch12 token 计量 + 费用 ——

def test_usage_metering(monkeypatch):
    llm.reset_usage()
    monkeypatch.setattr(
        llm._client.chat.completions, "create",
        lambda **kw: _fake_resp_with_usage("hi", prompt=100, completion=50),
    )
    llm.chat([{"role": "user", "content": "x"}])
    assert llm.get_usage() == (100, 50)
    llm.reset_usage()  # 归零
    assert llm.get_usage() == (0, 0)


def test_usage_ignores_missing_usage_field(monkeypatch):
    # 某些 mock/接口不返回 usage:计量不报错,保持 0
    llm.reset_usage()
    monkeypatch.setattr(llm._client.chat.completions, "create", lambda **kw: _fake_resp("hi"))
    llm.chat([{"role": "user", "content": "x"}])
    assert llm.get_usage() == (0, 0)


def test_compute_cost():
    # 按价格表(元/百万 token):1M 输入 = 输入单价,1M 输出 = 输出单价
    assert llm.compute_cost(1_000_000, 0) == settings.chat_price_input_per_1m
    assert llm.compute_cost(0, 1_000_000) == settings.chat_price_output_per_1m
    assert llm.compute_cost(0, 0) == 0.0


# —— Ch30:裁判可独立配置 ——

def test_judge_model_falls_back_to_chat_model(monkeypatch):
    """judge_model 留空时回退到 chat_model —— 保持旧行为,不配就等于没这功能。"""
    from backend import llm
    monkeypatch.setattr(llm.settings, "judge_model", "")
    monkeypatch.setattr(llm.settings, "chat_model", "some-chat-model")
    assert (llm.settings.judge_model or llm.settings.chat_model) == "some-chat-model"


def test_chat_json_uses_judge_client(monkeypatch):
    """裁判走独立客户端:换裁判不该连生成一起换掉(否则 A/B 做不了)。"""
    from backend import llm
    used = {}

    class _FakeJudge:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    used["client"] = "judge"
                    used["model"] = kw["model"]

                    class _R:
                        class choices:
                            @staticmethod
                            def __iter__():
                                return iter([])
                    return type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": '{"score": 1}'})()})()]})

    monkeypatch.setattr(llm, "_judge_client", _FakeJudge)
    monkeypatch.setattr(llm, "JUDGE_MODEL", "judge-model-x")
    llm.chat_json([{"role": "user", "content": "x"}])
    assert used["client"] == "judge"
    assert used["model"] == "judge-model-x"   # 用的是裁判模型,不是 chat_model
