# EvalFlow Ch21 实施计划:知识库地图性能修复

## 背景(对应 spec)

修 `GET /knowledge/map` 的 35s 超时:静态部分缓存 + 样本有界 + 超时可配。

## 任务清单

### Task 1:抽出 knowledge_map 模块 + 缓存

- [x] 新增 `backend/knowledge_map.py`:`_chunk_layout()` 缓存知识块 embedding + PCA 基底 + chunk 坐标(`global`,首次计算)。

### Task 2:样本问题有界

- [x] `_recent_unique_inputs(limit)`:近 `limit*3` 条候选 → 按 input 去重 → 截到 `MAX_QUERY_POINTS=100`。

### Task 3:超时可配

- [x] `config.py` 加 `embed_timeout=120`;`embedding.py` 用它;`.env.example` 补 `EMBED_MODEL`/`EMBED_TIMEOUT`。

### Task 4:端点改薄 + 测试

- [x] `main.py` 的 `knowledge_map` 改为调模块。
- [x] `tests/test_knowledge_map.py`:缓存命中(只 embed 一次)、去重 + 上限、返回结构。
- [x] 现有 85 后端测试全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 35s → 8s / 0.7s | 实机验证 |
| 知识块只嵌入一次 | Task 1/4 |
| 样本去重 + 上限 | Task 2/4 |
| 85 后端全绿 + 新增 | Task 4 |
