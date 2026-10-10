import json
import logging

from backend.logging_config import JsonFormatter


def _record(msg="hello", **extra):
    rec = logging.LogRecord(
        name="backend.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_json_formatter_includes_context_fields():
    fmt = JsonFormatter()
    out = json.loads(fmt.format(_record(run_id=7, trace_id=42, latency_ms=1234)))
    assert out["level"] == "INFO"
    assert out["event"] == "hello"
    assert out["run_id"] == 7
    assert out["trace_id"] == 42
    assert out["latency_ms"] == 1234


def test_json_formatter_omits_absent_fields():
    fmt = JsonFormatter()
    out = json.loads(fmt.format(_record()))
    assert "run_id" not in out and "trace_id" not in out and "latency_ms" not in out


def test_json_formatter_includes_exception():
    import sys

    fmt = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord(
            name="backend.test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=sys.exc_info(),
        )
    out = json.loads(fmt.format(rec))
    assert "ValueError" in out["exc"] and "boom" in out["exc"]
