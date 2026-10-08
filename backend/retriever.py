from backend.knowledge import KNOWLEDGE


def retrieve(query: str, top_k: int = 2) -> list[str]:
    """最小检索:关键词命中数越多排名越前。"""
    scored = []
    for k in KNOWLEDGE:
        hits = sum(1 for kw in k["keywords"] if kw in query)
        if hits > 0:
            scored.append((hits, k["text"]))
    scored.sort(key=lambda x: -x[0])
    return [text for _, text in scored[:top_k]]
