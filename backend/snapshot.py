"""可复现快照:发起 run 时把「复现上下文」一次性写进 Run.config,之后依赖改动不影响历史 run(Ch09)。"""
import hashlib
import json

from backend.config import settings
from backend.knowledge import KNOWLEDGE, KNOWLEDGE_VERSION
from backend.prompts import JUDGE_PROMPTS_VERSION, PIPELINE_PROMPT_VERSION


def config_top_k(config_str: str) -> int:
    """从 config 快照取 top_k,缺省/解析失败回退默认 2(兼容老 run 的空 config)。"""
    try:
        return int(json.loads(config_str or "{}").get("top_k", 2))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2


def config_retrieval(config_str: str) -> str:
    """从 config 取检索方式,缺省/非法回退 hybrid(Ch16 兼容老 run 无该字段)。"""
    try:
        v = json.loads(config_str or "{}").get("retrieval", "hybrid")
        return v if v in ("dense", "hybrid") else "hybrid"
    except (TypeError, ValueError, json.JSONDecodeError):
        return "hybrid"


def content_hash(items: list[dict]) -> str:
    """对一组 dict 做稳定哈希(与 dict/key 顺序无关),用于「内容是否变化」校验。"""
    normalized = [dict(sorted(it.items())) for it in items]
    normalized.sort(key=lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True))
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def build_snapshot(dataset_id: int, top_k: int, retrieval: str = "hybrid") -> dict:
    """组装 run 的复现上下文:用户配置 + 系统快照,一次性写进 Run.config。"""
    from backend.db import SessionLocal
    from backend.models import DatasetItem

    s = SessionLocal()
    rows = s.query(DatasetItem.input, DatasetItem.expected_output, DatasetItem.bucket) \
           .filter(DatasetItem.dataset_id == dataset_id).all()
    s.close()
    items = [{"input": i, "expected_output": e, "bucket": b} for i, e, b in rows]

    return {
        "top_k": top_k,
        "retrieval": retrieval,  # Ch16:dense|hybrid,记录「这次用哪种检索跑出来的」
        "knowledge_version": KNOWLEDGE_VERSION,
        "knowledge_hash": content_hash(KNOWLEDGE),
        "pipeline_prompt_version": PIPELINE_PROMPT_VERSION,
        "judge_prompt_version": JUDGE_PROMPTS_VERSION,
        "chat_model": settings.chat_model,
        "embed_model": settings.embed_model,
        "dataset_hash": content_hash(items),
        "item_count": len(items),
    }
