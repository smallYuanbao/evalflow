# EvalFlow Ch06 实施计划:多 run 对比评测

## 背景(对应 spec)

Ch05 指标升级到 6 个后,每次只能看**单个 run 的绝对分数**。Ch06 打通「可配置 + 对比」:

1. 发起评测时能配置 `top_k`(检索命中数)。
2. run 保存配置快照(`config` JSON),执行时**真正生效**。
3. 新增对比页 `/compare`,选多个 run 并排看各指标。

现状关键点:后端 `retriever.retrieve(query, top_k=2)` **已有** `top_k` 参数,但 `pipeline.run_pipeline(question)` 和 `run_service.execute_run` 把它写死了;前端 `createRun` 也把 `config` 写死成 `'{}'`。所以 Ch06 主要是「把 top_k 从发起评测一路流到检索」,外加一个对比视图。

## 任务清单

### Task 1:后端配置注入链路(pipeline + run_service)

- [x] `backend/pipeline.py`:`run_pipeline(question, top_k=2)` 加参数,透传给 `retrieve`。

```python
def run_pipeline(question: str, top_k: int = 2) -> dict:
    hits = retrieve(question, top_k=top_k)
    ...
```

- [x] `backend/run_service.py`:新增 `_config_top_k()`,从 `run.config` 取 top_k,缺省/解析失败回退 2;`execute_run` 调 `run_pipeline(it.input, top_k)`。

```python
def _config_top_k(config_str: str) -> int:
    try:
        return int(json.loads(config_str or "{}").get("top_k", 2))
    except (TypeError, ValueError, json.JSONDecodeError):
        return 2
```

### Task 2:GET /runs 补 config(列表回看)

- [x] `backend/main.py` `list_runs`:每行补 `config`(与 `POST /runs` 已收 config 呼应,列表能回看「这次用了什么配置」)。

### Task 3:后端测试

- [x] `tests/test_run_service.py`:3 处 mock 的 `run_pipeline` 签名从 `lambda q:` 改 `lambda q, top_k=2:`(execute_run 现在传两个参数);新增 `test_execute_run_passes_top_k_from_config`(config 设 `{"top_k": 5}`,断言 pipeline 收到的 top_k 是 5)。
- [x] `tests/test_api.py`:`run_pipeline` mock 同样改签名;`POST /runs` 用非空 config,断言 `GET /runs` 回看的 `config` 一致。

### Task 4:前端 api + types

- [x] `frontend/src/types.ts`:`Run` 补 `config?: string`。
- [x] `frontend/src/api/index.ts`:`createRun(dataset_id, config?)` 接收 config 对象,序列化进 body。

```ts
createRun: (dataset_id: number, config?: { top_k?: number }) =>
  request<Run>('/runs', { method: 'POST', data: { dataset_id, config: JSON.stringify(config ?? {}) } }),
```

### Task 5:RunsView(top_k 选择 + 多选 + 对比按钮)

- [x] 发起评测旁加 `InputNumber`(top_k,默认 2,范围 1~10);`start` 传 `api.createRun(sel, { top_k: topK })`。
- [x] run 表格加 `rowSelection`(多选),选中 ≥2 时「对比」按钮可用,点击跳 `/compare?ids=1,2,3`。

### Task 6:CompareView + 路由

- [x] 新 `frontend/src/views/CompareView.tsx`:
  - 从 URL `?ids=` 解析 id 列表,`Promise.all` 并发拉 `GET /runs/{id}`。
  - 指标集合 = 各 run `scores` key 的并集(保序)。
  - 对比表:行 = 指标(中文标签),列 = 每个 run,单元格 = 该 run 该指标均值。
  - 分组柱状图:每个指标一组,组内每个 run 一根柱(recharts 多 Bar)。
- [x] `frontend/src/App.tsx`:加 `<Route path="/compare" element={<CompareView />} />`。

### Task 7:前端测试

- [x] `RunsView.test.tsx`(新):渲染 run 列表 + top_k 输入框存在,「对比」按钮初始禁用。
- [x] `CompareView.test.tsx`(新):mock 两个 run 的 `getRun`,断言两个 Run 列头 + 指标行出现。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 指定 top_k 真正生效 | Task 1 + Task 3 的 top_k 流入测试 |
| config 快照可回看 | Task 2 + Task 3 的 config 断言 |
| 对比页并排对比 | Task 6 + Task 7 |
| 测试 + build 全绿 | Task 3 / 7 + 最后跑全量验证 |
