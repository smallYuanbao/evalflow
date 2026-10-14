# EvalFlow Ch30 设计:裁判可独立配置

## 定位

把 Ch28 的结论**落地成可执行的东西**——那章量出「换裁判让 context_recall 差 0.31」,
但当时代码里**裁判和生成共用一套配置**,换裁判必须连生成一起换,A/B 只能靠脚本 monkeypatch 硬做。

## 问题

```python
_client = OpenAI(api_key=settings.chat_api_key, base_url=settings.chat_base_url, ...)

def chat(...):      _create_with_retry(model=settings.chat_model, ...)      # 生成
def chat_json(...): _create_with_retry(model=settings.chat_model, ...)      # 裁判 ← 同一个
```

后果:
1. **做不了 A/B**:想换裁判就得改 `CHAT_MODEL`,那会**连被测系统的生成一起换掉**——
   两个变量同时动,对比失去意义。
2. **裁判不进快照**:快照只记 `chat_model`。换个裁判跑出来的分数,和历史的不可比,
   但**快照上看不出来**(Ch29 刚给「对比前提」加了校验,裁判正是前提之一)。

## 决策

### 决策 1:三个独立配置,留空回退

```python
judge_base_url: str = ""
judge_api_key: str = ""
judge_model: str = ""
```

`JUDGE_MODEL = settings.judge_model or settings.chat_model` —— **不配就等于没这功能**,
现有行为和测试全部不变。

**理由**:引入新配置最怕「默认值改变了既有行为」。回退到原值是最安全的设计。

### 决策 2:`chat_json` 走 `_judge_client`

`chat_json` 目前**只被 judge 用**(`evaluators._judge`),所以让它整个走裁判客户端是语义正确的。
`chat`(生成)继续走 `_client`。

`_create_with_retry(client, **kwargs)` 把客户端变成参数——**一个出口、两种仪器**。

**已知局限(写在注释里)**:熔断器是模块级单例,两个供应商共用一个——
一个挂了会连带影响另一个。demo 量级可接受;真要分开得按 client 建各自的熔断器。

### 决策 3:裁判模型进快照

`Run.config` 增加 `judge_model`。Run 详情页「复现上下文」加一行「裁判模型」,
悬停解释「换裁判等于换尺子,历史分数不再可比」。

**理由**:裁判是**测量仪器**。Ch28 已经证明它对结果的影响量级——
不记它的快照,和「不记知识库版本」是同一类缺陷。

## 验收

- [x] 不配 `JUDGE_*` 时行为完全不变(回退到 `CHAT_*`),97 后端测试全绿。
- [x] `chat_json` 确实用 `_judge_client` + `JUDGE_MODEL`(单测断言)。
- [x] 快照含 `judge_model`;前端展示。
- [x] `.env.example` 记录三个新配置与理由。

## 端到端验证(真实跑,不是单测)

配 `JUDGE_*` 指向通义,走**生产流程**(不是 Ch28 那个 monkeypatch 脚本)跑一次评测,
同数据集对比裁判切换前后:

| 指标 | deepseek-chat | qwen3.8-max | Δ |
|---|---|---|---|
| recall / hit_at_k / mrr / rejection | — | — | **0.000** |
| context_precision | 0.450 | 0.527 | +0.077 |
| **context_recall** | 0.500 | 0.807 | **+0.307** |
| faithfulness | 0.100 | 0.033 | −0.067 |
| answer_relevance | 0.600 | 0.300 | **−0.300** |
| answer_correctness | 0.400 | 0.333 | −0.067 |

快照确认:`chat_model=deepseek-chat` / **`judge_model=qwen3.8-max-0902`** —— 分别记录。

**两点值得注意**:
1. **机械指标的 Δ 全是 0.000** —— 它们不调 LLM,裁判换了也无感。
   这是**反向验证**:差异确实来自裁判,不是数据。
2. **`context_recall` +0.307** —— 与 Ch28 在**另一批样本**上测到的 +0.31 几乎一致。
   两次独立测量同一个量级,结论更稳。

## 本章不做

- **熔断器按 client 分开**:需要重构熔断器为「按 client 实例化」,属独立改动。
- **多裁判投票 / 平均**:那是另一套设计(用多个裁判降方差),不是配置问题。
