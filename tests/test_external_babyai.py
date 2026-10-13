"""Ch26:评测外部系统 baby-ai 的适配器与快照记录。"""
from backend import external_babyai, snapshot


def test_run_pipeline_babyai_assembles_output(monkeypatch):
    class _Resp:
        @staticmethod
        def raise_for_status(): pass
        @staticmethod
        def json():
            return {"answer": "物理降温", "references": [{"id": "a", "text": "证据一"}, {"id": "b", "text": "证据二"}]}

    captured = {}

    def _post(url, json=None, timeout=None):
        captured["url"], captured["json"] = url, json
        return _Resp()

    monkeypatch.setattr(external_babyai.requests, "post", _post)
    out = external_babyai.run_pipeline_babyai("宝宝发烧怎么办")

    assert out["output"] == "物理降温"
    assert out["retrieved_context"] == "证据一\n证据二"
    assert [h["text"] for h in out["hits"]] == ["证据一", "证据二"]
    assert captured["url"].endswith("/api/chat")
    # 每次全新 session_id + 不带 history(避免题间记忆污染)
    assert captured["json"]["session_id"].startswith("eval-")
    assert "history" not in captured["json"]


def test_external_snapshot_local(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "eval_target", "local")
    assert snapshot._external_snapshot() == {"target": "local"}


def test_external_snapshot_records_meta(monkeypatch):
    monkeypatch.setattr(snapshot.settings, "eval_target", "babyai")
    monkeypatch.setattr(external_babyai, "fetch_meta", lambda: {"commit": "abc1234", "model": "m"})
    ext = snapshot._external_snapshot()
    assert ext["target"] == "babyai"
    assert ext["meta"]["commit"] == "abc1234"
    assert ext["meta_error"] is None


def test_external_snapshot_marks_unknown(monkeypatch):
    """拿不到对方状态时必须显式标记——静默记空会让人误信「这次可与历史对比」。"""
    monkeypatch.setattr(snapshot.settings, "eval_target", "babyai")
    monkeypatch.setattr(external_babyai, "fetch_meta", lambda: None)
    ext = snapshot._external_snapshot()
    assert ext["meta"] is None
    assert ext["meta_error"]  # 非空 = 显式告知「未知」
