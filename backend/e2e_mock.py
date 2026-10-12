"""E2E 确定性假实现(Ch14):E2E_MOCK=1 时替换 run_pipeline 与 5 个 LLM judge。

目的:Playwright 端到端测主流程(造集 → 发评测 → 看结果)时不调真实 LLM / Ollama / chroma,
不烧钱、不依赖外部服务、结果确定可断言。recall(机械关键词)与 rejected(拒答)保持真实,
它们本来就不调 LLM。
"""


def mock_run_pipeline(input_text: str, top_k: int = 2, retrieval: str = "hybrid") -> dict:
    """替换 backend.pipeline.run_pipeline:返回固定的检索证据 + 回答。"""
    return {
        "output": "物理降温并观察体温变化,持续高热需就医。",
        "retrieved_context": "物理降温 观察体温 就医",
        "hits": [{"text": "物理降温", "score": 0.9}, {"text": "就医", "score": 0.8}],
    }


def mock_judge(*args, **kwargs) -> dict:
    """替换 5 个 LLM judge:返回固定分数与原因。"""
    return {"score": 0.8, "reason": "e2e mock"}
