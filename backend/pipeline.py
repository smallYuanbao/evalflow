def run_pipeline(question: str) -> dict:
    """检索 + 生成。Ch01 mock:返回固定结构,第 2 章换真实实现(签名不变)。"""
    return {
        "output": f"(mock)对「{question}」的回答",
        "retrieved_context": "(mock)检索到的证据片段",
    }
