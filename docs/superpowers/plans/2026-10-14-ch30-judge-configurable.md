# EvalFlow Ch30 实施计划:裁判可独立配置

## 背景(对应 spec)

Ch28 量出「换裁判指标动 0.31」,但代码里裁判和生成共用配置,A/B 只能靠脚本硬做。

## 任务清单

- [x] `config.py` 加 `judge_base_url` / `judge_api_key` / `judge_model`(留空回退 `CHAT_*`)。
- [x] `llm.py` 加 `_judge_client` + `JUDGE_MODEL`;`_create_with_retry(client, **kw)` 参数化;
      `chat` 走 `_client`,`chat_json` 走 `_judge_client`。
- [x] `snapshot.py` 记录 `judge_model`;RunDetailView 加「裁判模型」行 + 悬停解释。
- [x] `.env.example` 补三个配置与理由。
- [x] 测试:回退行为 + `chat_json` 用裁判客户端;修正 3 个 mock `_client` 的老测试。
- [x] 后端 97 / 前端 33 / build 全绿。

## 验收对照

| spec 验收项 | 覆盖 |
|---|---|
| 不配时行为不变 | 任务 1/5 |
| chat_json 用裁判客户端 | 任务 2/5 |
| 快照 + 前端展示 | 任务 3 |
| 97 测试全绿 | 任务 5 |
