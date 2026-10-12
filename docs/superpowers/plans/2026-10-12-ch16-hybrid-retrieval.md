# EvalFlow Ch16 实施计划:混合检索(dense + BM25 + RRF)

## 背景(对应 spec)

给检索加关键词一路:手写 BM25 + RRF 与 chroma dense 融合;retrieval 作为 run 配置进快照,支持 dense/hybrid 切换。

## 任务清单

### Task 1:BM25 稀疏检索

- [x] 新增 `backend/bm25.py`:`_tokenize`(字符 bigram)+ `BM25` 类(建倒排索引、标准 BM25 打分、`search(query, top_k)` 返回 `[(id, text, score)]`)。
- [x] 参数 k1=1.5 / b=0.75,IDF 用标准平滑公式。

### Task 2:混合检索 + RRF

- [x] `backend/retriever.py` 拆出 `_dense_hits(query, top_k)`(返回含 id);`retrieve` 改名 `retrieve_dense`(dense-only)。
- [x] 新增 `hybrid_retrieve(query, top_k)`:dense + BM25 两路 RRF(k=60)融合取 top-k,返回 `[{text, score}]`。

### Task 3:retrieval 进配置与快照

- [x] `backend/snapshot.py` 加 `config_retrieval(config_str)`(非法回退 hybrid);`build_snapshot` 加 `retrieval` 字段。
- [x] `backend/main.py` `create_run` 传 `config_retrieval(body.config)` 进快照。
- [x] `backend/pipeline.py` `run_pipeline(question, top_k, retrieval)` 按 retrieval 分发;`run_service.py` 读快照 retrieval 并下传。
- [x] `backend/e2e_mock.py` `mock_run_pipeline` 兼容新增 `retrieval` 参数。

### Task 4:后端测试

- [x] `tests/test_bm25.py`:关键词命中排前、无关词不命中。
- [x] `tests/test_hybrid.py`(或扩展):两路命中者排最前、retrieval 写进快照、dense/hybrid 分发。
- [x] 更新 `test_retriever.py`(`retrieve` → `retrieve_dense`)、`test_pipeline.py`(monkeypatch 目标 + 补 dense 模式)。
- [x] 现有 65 后端测试全绿(现 72 = 65 + 7 新增)。

### Task 5:前端

- [x] `RunsView.tsx` 加「检索方式」下拉,`api.createRun` config 带 `retrieval`。
- [x] `api/index.ts` `createRun` config 类型加 `retrieval?`。
- [x] `RunDetailView.tsx`:复现上下文加「检索方式」行;命中标签「相似度」→「融合分」。

### Task 6:前端测试与构建

- [x] 相关单测补检索方式断言(13 通过);`npm run build` 通过;e2e 主流程仍绿(combobox 改 first())。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| BM25 关键词命中排前 | Task 1/4 |
| hybrid RRF 融合 | Task 2/4 |
| retrieval 进快照 + 可切换 | Task 3/4 |
| 65 后端测试全绿 + 新增 | Task 4 |
| 前端暴露检索方式 | Task 5/6 |
