from backend import llm
from backend.retriever import retrieve


def run_pipeline(question: str, top_k: int = 2) -> dict:
    """检索 + 生成(真实 LLM)。检索返回 [{text, score}],证据拼接 + 命中原样带回。"""
    hits = retrieve(question, top_k=top_k)
    context = "\n".join(f"[{i+1}] {h['text']}" for i, h in enumerate(hits)) or "(无证据)"
    output = llm.chat([
        {"role": "system", "content": "你是育儿客服助手,只依据给定证据回答,证据没有就说不清楚。"},
        {"role": "user", "content": f"证据:\n{context}\n\n问题:{question}"},
    ])
    return {"output": output, "retrieved_context": context, "hits": hits}
