FAITHFULNESS_PROMPT = """你是 RAG 评测裁判,判断「回答」是否忠实于「证据」:回答里每个论断都要能在证据里找到依据,不编造、不夸大。

证据:
{context}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""
