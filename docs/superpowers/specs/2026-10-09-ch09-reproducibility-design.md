# EvalFlow Ch09 设计:可复现性增强

## 目标

评测平台的核心价值是「结果可信、可复现」。现在打开一个历史 run,只能看到 `top_k`,回答不了「当时用的是哪版知识库、哪版 prompt、哪个模型、哪批样本」——知识库/prompt/评测集一改,历史 run 就失去了可追溯性。

Ch09 把「复现上下文」在**发起 run 时一次性快照**进 `Run.config`,之后这些依赖再怎么改,历史 run 仍能还原当时的完整上下文。

## 现状问题

| 维度 | 现状 | 问题 |
|---|---|---|
| 用户配置 | `config` 只存 `{"top_k"}` | 无系统快照 |
| 知识库 | [knowledge.py](backend/knowledge.py) 硬编码,无版本 | 改了内容无从追溯 |
| prompt | [prompts.py](backend/prompts.py) 5 个 judge prompt + [pipeline.py](backend/pipeline.py) 1 个 system prompt,无版本 | 分散、无版本 |
| 模型 | `chat_model` / `embed_model` 在 settings,不进快照 | 换模型后历史对不上 |
| 数据集 | run 只存 `dataset_id`,样本改了历史对不上 | 无快照 |

## 核心方案

`POST /runs` 时由**后端权威组装**完整快照(前端仍只传 `top_k`),写进 `Run.config`:

```json
{
  "top_k": 3,                 // 用户配置
  "knowledge_version": "v1",  // 系统快照(以下)
  "knowledge_hash": "<md5>",
  "prompt_version": "v1",
  "chat_model": "deepseek-chat",
  "embed_model": "bge-m3",
  "dataset_hash": "<md5>",
  "item_count": 7
}
```

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 快照存哪 | 统一塞进现有 `Run.config`(JSON) | 新增字段要迁移表;config 本就是「配置快照」,扩展它语义一致,前端 `configLabel` 兼容 |
| 知识库版本 | 显式 `KNOWLEDGE_VERSION` **+** 内容哈希 `knowledge_hash` 双存 | 版本号给人读,哈希保证「内容与版本一致」;面试讲得出为什么两个都要 |
| prompt 版本 | 显式 `PROMPTS_VERSION`,并把 pipeline system prompt 迁入 prompts.py 统一管理 | 一个版本管全部 prompt,避免「改了 prompt 忘 bump」分散在多处 |
| 数据集快照 | 内容哈希 `dataset_hash` + `item_count` | 能检测样本是否被改;完整版本化(DatasetVersion 表)是大改,留作后续 |
| 快照组装时机 | 后端 `create_run` 组装(前端只传 top_k) | 前端零改动,系统快照由后端权威生成,防前端漏传/伪造 |
| top_k 解析归属 | 抽到 `snapshot.py` 的 `config_top_k`,run_service 与 main 共用 | 消除 `_config_top_k` 重复 |

## 需要改动(实现时细化)

1. `backend/prompts.py`:加 `PROMPTS_VERSION = "v1"`,加 `PIPELINE_SYSTEM_PROMPT`(从 pipeline.py 迁入)。
2. `backend/knowledge.py`:加 `KNOWLEDGE_VERSION = "v1"`。
3. `backend/snapshot.py`(新):`content_hash()` 稳定哈希 + `config_top_k()` + `build_snapshot(dataset_id, top_k)`。
4. `backend/pipeline.py`:system prompt 改从 prompts.py 引。
5. `backend/main.py` `create_run`:解析 top_k → `build_snapshot` → 存 config。
6. `backend/run_service.py`:删 `_config_top_k`,改用 `snapshot.config_top_k`。
7. 前端 `RunDetailView`:加「复现上下文」卡片,展示快照字段(列表页保持只显示 top_k,不挤)。

## 本章不做

- 数据集完整版本化(DatasetVersion 表、每次修改生成新版本)——留后续章节。
- prompt 内容哈希(只做显式版本号)。
- 知识库可管理化(上传/导入/在线编辑)——Ch09 只加版本标识,不动「硬编码」本身。
