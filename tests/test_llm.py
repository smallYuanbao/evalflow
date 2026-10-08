from types import SimpleNamespace

from backend import llm


def _fake_resp(content: str):
    # 模拟 openai 响应结构:resp.choices[0].message.content
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


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
