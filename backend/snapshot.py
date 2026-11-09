"""可复现快照:发起 run 时把「复现上下文」一次性写进 Run.config,之后依赖改动不影响历史 run(Ch09)。"""
import hashlib
import json

from backend.config import settings
from backend.knowledge import KNOWLEDGE, KNOWLEDGE_VERSION
from backend.prompts import JUDGE_PROMPTS_VERSION, PIPELINE_PROMPT_VERSION


MAX_TOP_K = 20  # top_k 上限:前端 max=10,这里留余量;再大也没意义(知识库才 23 条)


def config_top_k(config_str: str) -> int:
    """从 config 快照取 top_k,缺省/解析失败回退默认 2(兼容老 run 的空 config)。

    越界值钳制到 [1, MAX_TOP_K]:前端 InputNumber 的 min/max 只在失焦时生效,
    且 API 可绕过前端,所以校验必须落在服务端(Ch23)。
    """
    try:
        v = int(json.loads(config_str or "{}").get("top_k", 2))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2
    return min(max(v, 1), MAX_TOP_K)


def config_retrieval(config_str: str) -> str:
    """从 config 取检索方式,缺省/非法回退 hybrid(Ch16 兼容老 run 无该字段)。"""
    try:
        v = json.loads(config_str or "{}").get("retrieval", "hybrid")
        return v if v in ("dense", "bm25", "hybrid") else "hybrid"
    except (TypeError, ValueError, json.JSONDecodeError):
        return "hybrid"


def effective_retrieval(requested: str, external: dict) -> str:
    """外部被测系统自己决定检索策略时,以它的 /api/meta 为准。

    ecom 的 `top_k` / `retrieval` 参数不生效(见 external_ecom 文档),如果
    快照继续记请求值,历史 run 会全部标成 hybrid,而实际跑的是 dense——
    "这次用哪种检索"这个复现字段就失真了。
    """
    actual = (external.get("meta") or {}).get("retrieval_strategy")
    return actual if actual in ("dense", "bm25", "hybrid") else requested


def content_hash(items: list[dict]) -> str:
    """对一组 dict 做稳定哈希(与 dict/key 顺序无关),用于「内容是否变化」校验。"""
    normalized = [dict(sorted(it.items())) for it in items]
    normalized.sort(key=lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True))
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _external_snapshot() -> dict:
    """被测系统(外部)的状态(Ch26)。local 时只是个标记;外部系统要连过去取它的 meta。

    **拿不到就显式标 meta_error,绝不用空值假装已知**——静默记空会让人误信
    「这次结果可与历史对比」,比不记更危险。
    """
    if settings.eval_target == "babyai":
        from backend.external_babyai import fetch_meta

        base_url = settings.babyai_base_url
    elif settings.eval_target == "ecom":
        from backend.external_ecom import fetch_meta

        base_url = settings.ecom_base_url
    else:
        return {"target": settings.eval_target}

    meta = fetch_meta()
    return {
        "target": settings.eval_target,
        "base_url": base_url,
        "meta": meta,
        "meta_error": None if meta else "拿不到被测系统状态(/api/meta 不可达),本次结果不可与历史对比",
    }


def build_snapshot(dataset_id: int, top_k: int, retrieval: str = "hybrid") -> dict:
    """组装 run 的复现上下文:用户配置 + 系统快照,一次性写进 Run.config。"""
    from backend.db import SessionLocal
    from backend.models import DatasetItem

    s = SessionLocal()
    rows = s.query(DatasetItem.input, DatasetItem.expected_output, DatasetItem.bucket) \
           .filter(DatasetItem.dataset_id == dataset_id).all()
    s.close()
    items = [{"input": i, "expected_output": e, "bucket": b} for i, e, b in rows]

    external = _external_snapshot()  # Ch26:被测系统(外部)的状态
    return {
        "top_k": top_k,
        # Ch16:记录「这次用哪种检索跑出来的」;外部系统自己决定时以它的 meta 为准
        "retrieval": effective_retrieval(retrieval, external),
        "external": external,
        "knowledge_version": KNOWLEDGE_VERSION,
        "knowledge_hash": content_hash(KNOWLEDGE),
        "pipeline_prompt_version": PIPELINE_PROMPT_VERSION,
        "judge_prompt_version": JUDGE_PROMPTS_VERSION,
        "chat_model": settings.chat_model,
        # Ch30:裁判也是「仪器」的一部分。换裁判 = 换尺子,历史对比就不成立了——
        # 所以必须和知识库/prompt 版本一样记进快照(Ch28 实测换裁判能让指标动 0.31)。
        "judge_model": settings.judge_model or settings.chat_model,
        "embed_model": settings.embed_model,
        "dataset_hash": content_hash(items),
        "item_count": len(items),
    }
