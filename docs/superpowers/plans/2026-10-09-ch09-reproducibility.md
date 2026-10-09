# EvalFlow Ch09 实施计划:可复现性增强

## 背景(对应 spec)

评测平台要「结果可复现」:历史 run 要能回答「当时用的哪版知识库/prompt/模型/样本」。方案是 `POST /runs` 时后端把「复现上下文」快照进 `Run.config` JSON,前端在详情页展示。

**关键现状(决定实现方式)**:
- `Run.config` 是 Text JSON,`run_service._config_top_k` 已从它解析 top_k(抽到 snapshot.py 共用)。
- `test_api.py:56` 断言 `config == '{"top_k": 3}'`,本次改动需更新为「解析后断言快照字段」。
- `test_run_service.py` 只做行为断言,不直接引用 `_config_top_k`,抽函数不破坏。

## 任务清单

### Task 1:prompts / knowledge 加版本标识

- [x] `backend/prompts.py`:加 `PROMPTS_VERSION = "v1"`,并把 pipeline 的 system prompt 迁入为 `PIPELINE_SYSTEM_PROMPT`。
- [x] `backend/knowledge.py`:加 `KNOWLEDGE_VERSION = "v1"`。
- [x] `backend/pipeline.py`:system prompt 改从 prompts.py 引(不再内联)。

### Task 2:新增 snapshot.py(哈希 + 快照组装)

- [x] `content_hash(items)`:对 list[dict] 做与顺序/key 无关的稳定 md5(用于内容变化校验)。
- [x] `config_top_k(config_str)`:从 run_service 迁移,缺省/解析失败回退 2。
- [x] `build_snapshot(dataset_id, top_k)`:读样本算 `dataset_hash`/`item_count`,连同 `knowledge_version`/`knowledge_hash`/`prompt_version`/`chat_model`/`embed_model` 组装成 dict。

### Task 3:create_run 组装快照 + run_service 复用

- [x] `backend/main.py` `create_run`:解析 top_k → `build_snapshot` → `json.dumps` 存进 `Run.config`。
- [x] `backend/run_service.py`:删 `_config_top_k`,改 `from backend.snapshot import config_top_k`。

### Task 4:前端详情页展示「复现上下文」

- [x] `frontend/src/views/RunDetailView.tsx`:加「复现上下文」卡片(antd `Descriptions`),解析 config 展示 top_k / 知识库版本+哈希 / prompt 版本 / 模型 / 数据集哈希+样本数;老 run(无快照字段)显示 `—`。
- [x] 列表页 `RunsView` configLabel 保持只显示 top_k(不挤)。

### Task 5:测试

- [x] 更新 `tests/test_api.py`:config 断言改为解析后校验 `top_k` + 快照字段。
- [x] 新增 `tests/test_snapshot.py`:content_hash 稳定/敏感、config_top_k 默认/异常、build_snapshot 字段完整。
- [x] 新增 `RunDetailView.test.tsx` 用例:带快照的 config 渲染出「复现上下文」字段。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| config 快照含 7 维上下文 | Task 2 + 3 |
| 知识库/prompt 有版本标识 | Task 1 |
| 数据集内容哈希可检测样本变化 | Task 2 + 5 |
| 历史 run 可回看完整上下文 | Task 4 |
| 不破坏老 run(无快照)与现有行为 | Task 3(解析回退 2)+ Task 4(`—`) |

## 本章不做

- 数据集版本化(DatasetVersion 表)、知识库在线管理、prompt 内容哈希(spec 已明确)。
