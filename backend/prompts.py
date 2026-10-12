# 版本标识:prompt 改动必须 bump 版本,保证历史 run 的 prompt 可追溯(Ch09 可复现)。
# Ch19 拆分:生成 prompt 与 judge prompt 各自独立版本,否则「模型变了还是评判标准变了」分不清。
PIPELINE_PROMPT_VERSION = "v1"
JUDGE_PROMPTS_VERSION = "v1"

# pipeline 生成阶段的 system prompt(从 pipeline.py 迁入,统一在这里管版本)
PIPELINE_SYSTEM_PROMPT = "你是育儿客服助手,只依据给定证据回答,证据没有就说不清楚。"

FAITHFULNESS_PROMPT = """你是 RAG 评测裁判,判断「回答」是否忠实于「证据」:回答里每个论断都要能在证据里找到依据,不编造、不夸大。

证据:
{context}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""

CONTEXT_PRECISION_PROMPT = """你是 RAG 评测裁判,判断「证据」里有多少是真正相关、有助于回答问题的(噪声越少、精度越高)。

问题:
{question}

证据:
{context}

只输出 JSON,格式:{{"score": <0到1的浮点数,表示相关有用的证据占比>, "reason": "<一句话理由>"}}"""

CONTEXT_RECALL_PROMPT = """你是 RAG 评测裁判,判断「证据」是否覆盖了回答问题所需的全部要点(漏检越少、召回越高)。

问题:
{question}

标准答案要点:
{expected}

证据:
{context}

只输出 JSON,格式:{{"score": <0到1的浮点数,表示要点被证据覆盖的比例>, "reason": "<一句话理由>"}}"""

ANSWER_RELEVANCE_PROMPT = """你是 RAG 评测裁判,判断「回答」是否切题:是否直接回应了问题,有没有跑题、啰嗦、答非所问。

问题:
{question}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""

ANSWER_CORRECTNESS_PROMPT = """你是 RAG 评测裁判,判断「回答」与「标准答案要点」的语义一致程度(同义表达也算对,不要求逐字)。

问题:
{question}

标准答案要点:
{expected}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""
