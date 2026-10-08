from backend import llm
from backend.retriever import retrieve


def run_pipeline(question: str) -> dict:
    """检索 + 生成(真实 LLM)。签名不变,内部从 mock 换成真实现。"""
    context_list = retrieve(question)
    context = "\n".join(f"[{i+1}] {t}" for i, t in enumerate(context_list)) or "(无证据)"
    output = llm.chat([
        {"role": "system", "content": "你是育儿客服助手,只依据给定证据回答,证据没有就说不清楚。"},
        {"role": "user", "content": f"证据:\n{context}\n\n问题:{question}"},
    ])
    return {"output": output, "retrieved_context": context}
