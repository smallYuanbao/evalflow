# 版本标识:prompt 改动必须 bump 版本,保证历史 run 的 prompt 可追溯(Ch09 可复现)。
# Ch19 拆分:生成 prompt 与 judge prompt 各自独立版本,否则「模型变了还是评判标准变了」分不清。
PIPELINE_PROMPT_VERSION = "v1"
# v2(2026-10-18):拒答从「词表机械判定」升级为「词表 + judge 双信号」,
# 判定标准变了 → 历史 run 的 rejection 不可与新 run 直接比较。
JUDGE_PROMPTS_VERSION = "v2"

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

标准答案要点（`/` 分隔要点组，组内 `|` 表示任选其一；按覆盖比例评分）:
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

标准答案要点（`/` 分隔要点组，组内 `|` 表示任选其一；覆盖每组任一说法即可，不要求逐字）:
{expected}

回答:
{answer}

只输出 JSON,格式:{{"score": <0到1的浮点数>, "reason": "<一句话理由>"}}"""

# 拒答判定(Ch27 的机械词表 + 这里的 judge,组成「双信号」)。
# 为什么要 judge:词表只能看措辞,分不清「口头说超出范围、实际仍作答」——
# 实测 baby-ai 说过「超出了我的范围」然后照样给出爬虫教程,词表会误判成拒答。
# 反过来,同一句话换个说法(「可不归我管」)词表又会漏判。judge 看的是有没有实质回答。
REJECTION_PROMPT = """你是 RAG 评测裁判,判断「回答」是否拒绝了回答用户的「问题」。

拒答的定义:明确表示无法/不回答、说明知识库里没有相关资料、或让用户去别处/问别人。
以下情况**不算**拒答:
- 开头说了「超出范围/只能回答育儿问题」,但随后仍然给出了针对问题的实质内容或操作建议;
- 只介绍了自己的身份,没有真正回答问题(这算拒答);
- 给出了部分通用建议就算作答,不算拒答。

问题:
{question}

回答:
{answer}

只输出 JSON,格式:{{"score": 1 表示拒答,0 表示未拒答, "reason": "<一句话理由>"}}"""
