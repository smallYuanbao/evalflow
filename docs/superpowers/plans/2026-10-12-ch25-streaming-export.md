# EvalFlow Ch25 实施计划:导出改为流式

## 背景(对应 spec)

两端都不再缓冲整份文件:后端 `StreamingResponse` + `yield_per`,前端浏览器原生下载。

## 任务清单

### Task 1:后端流式

- [x] `stats.py` 加 `run_export_csv_stream`(逐行 yield + `yield_per(500)`);删掉非流式的 `run_export_csv`。
- [x] `main.py` 端点改 `StreamingResponse` + `_with_bom`(首块加 BOM);404 判定独立出来。

### Task 2:前端原生下载

- [x] `client.ts` 导出 `BASE` + `exportRunCsvUrl()`(带密钥时用 `?token=`)。
- [x] `RunDetailView.exportCsv` 改为 `<a href=接口>` 触发;`api.exportRunCsv` 移除。

### Task 3:鉴权例外

- [x] `auth_middleware`:仅对 `/export` 端点额外接受 `?token=`,并注明代价。

### Task 4:测试

- [x] `test_stats.py` 改用流式函数。
- [x] 实测响应 `transfer-encoding: chunked`;404 仍正常。
- [x] 后端 87 / 前端 33 / build / e2e 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 真流式(chunked) | Task 1/4 |
| 前端不再拼 Blob | Task 2 |
| `?token=` 鉴权 | Task 3 |
| 404 正常 | Task 1/4 |
