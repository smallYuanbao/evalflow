from backend import llm
from backend.prompts import PIPELINE_SYSTEM_PROMPT
from backend.retriever import hybrid_retrieve, retrieve_dense


def run_pipeline(question: str, top_k: int = 2, retrieval: str = "hybrid") -> dict:
    """检索 + 生成(真实 LLM)。检索返回 [{text, score}],证据拼接 + 命中原样带回。

    retrieval:hybrid(默认,dense + BM25 + RRF)/ dense(纯向量,Ch04 原行为)。
    """
    hits = (hybrid_retrieve if retrieval == "hybrid" else retrieve_dense)(question, top_k=top_k)
    context = "\n".join(f"[{i+1}] {h['text']}" for i, h in enumerate(hits)) or "(无证据)"
    output = llm.chat([
        {"role": "system", "content": PIPELINE_SYSTEM_PROMPT},
        {"role": "user", "content": f"证据:\n{context}\n\n问题:{question}"},
    ])
    return {"output": output, "retrieved_context": context, "hits": hits}
