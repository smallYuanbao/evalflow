"""Ch07:ecom-agent 适配器与快照。"""
import requests

from backend import external_ecom, snapshot


class _Resp:
    def __init__(self, status: int = 200, data: dict | None = None):
        self.status_code = status
        self._data = data or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self._data


def test_run_pipeline_ecom_maps_answer_and_hits(monkeypatch):
    captured = {}

    def _post(url, json=None, timeout=None):
        captured["url"], captured["json"] = url, json
        return _Resp(
            200,
            {
                "answer": "订单 1001 已签收。",
                "references": [{"id": "a", "text": "证据一"}],
                "hits": [
                    {"id": "a", "text": "证据一", "rank": 1, "score": 0.9, "cited": True},
                    {"id": "b", "text": "证据二", "rank": 2, "score": None, "cited": False},
                ],
            },
        )

    monkeypatch.setattr(external_ecom.requests, "post", _post)
    monkeypatch.setattr(external_ecom, "_throttle", lambda: None)

    out = external_ecom.run_pipeline_ecom("订单1001到哪了")

    assert out["output"] == "订单 1001 已签收。"
    assert out["retrieved_context"] == "证据一"
    assert [h["text"] for h in out["hits"]] == ["证据一", "证据二"]
    assert out["hits"][1]["score"] == 0.0
    assert captured["url"].endswith("/api/eval/chat")
    assert captured["json"] == {"message": "订单1001到哪了"}


def test_run_pipeline_retries_5xx(monkeypatch):
    responses = [_Resp(500), _Resp(200, {"answer": "ok", "references": [], "hits": []})]
    calls = []

    def _post(*args, **kwargs):
        calls.append(1)
        return responses.pop(0)

    monkeypatch.setattr(external_ecom.requests, "post", _post)
    monkeypatch.setattr(external_ecom, "_throttle", lambda: None)
    monkeypatch.setattr(external_ecom.time, "sleep", lambda _: None)

    out = external_ecom.run_pipeline_ecom("q")

    assert out["output"] == "ok"
    assert len(calls) == 2


def test_run_pipeline_does_not_retry_4xx(monkeypatch):
    calls = []

    def _post(*args, **kwargs):
        calls.append(1)
        return _Resp(400)

    monkeypatch.setattr(external_ecom.requests, "post", _post)
    monkeypatch.setattr(external_ecom, "_throttle", lambda: None)

    try:
        external_ecom.run_pipeline_ecom("q")
    except requests.HTTPError:
        pass
    else:                                            # pragma: no cover
        raise AssertionError("4xx 应该直接失败")

    assert len(calls) == 1


def test_fetch_meta_success_and_failure(monkeypatch):
    monkeypatch.setattr(
        external_ecom.requests,
        "get",
        lambda *a, **kw: _Resp(200, {"kb_version": "abc123"}),
    )
    assert external_ecom.fetch_meta() == {"kb_version": "abc123"}

    def _boom(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(external_ecom.requests, "get", _boom)
    assert external_ecom.fetch_meta() is None


def test_external_snapshot_records_ecom_meta(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "eval_target", "ecom")
    monkeypatch.setattr(
        external_ecom, "fetch_meta", lambda: {"kb_version": "abc123", "chat_model": "m"}
    )

    ext = snapshot._external_snapshot()

    assert ext["target"] == "ecom"
    assert ext["base_url"] == snapshot.settings.ecom_base_url
    assert ext["meta"]["kb_version"] == "abc123"
    assert ext["meta_error"] is None


def test_external_snapshot_ecom_unknown(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "eval_target", "ecom")
    monkeypatch.setattr(external_ecom, "fetch_meta", lambda: None)

    ext = snapshot._external_snapshot()

    assert ext["meta"] is None
    assert ext["meta_error"]
