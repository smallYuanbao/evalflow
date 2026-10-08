# EvalFlow Ch01 设计:评测数据地基(数据模型 + demo 管线)

## 目标

RAG 评测平台第一章:跑通数据地基。不做评测流程、不做 evaluator、不做前端。

验收标准:
1. 6 张表建好,能用 SQL 查到表结构。
2. 跑 `seed.py`,能插入 1 个 dataset + 若干 item + 几条 trace + score,且外键关联正确。
3. 跑 `pipeline.run_pipeline("测试")` 能返回 `{"output": str, "retrieved_context": str}`(先 mock,不调真实模型)。

## 技术栈(定死,不可自行更换)

- Python 3.12 + FastAPI + SQLAlchemy + SQLite
- 依赖管理:uv
- 模型接入:OpenAI 兼容协议(DeepSeek 等),judge 温度固定 0——本章管线先 mock,不调真实模型,**不需要任何密钥**;第 2 章接真实 judge 时再向用户要密钥
- 前端(第 3 章才做):技术栈待定(用户最熟的框架),本章不涉及

## 架构:单进程

一条命令(`scripts/dev.sh`)拉起 FastAPI(:8000)。SQLite 单文件 `data/eval.db`,SQLAlchemy 管理 ORM。

本章数据流只有一条:seed 脚本 → 直接写 SQLite → 用 SQL 验证。跑评测的 run 流程(第 2 章)才引入 FastAPI 业务接口。

## 目录结构

```
backend/
  main.py              # FastAPI 入口(GET /health)
  config.py            # pydantic-settings 读 .env
  db.py                # SQLAlchemy engine + session 工厂
  models.py            # 6 张表 ORM 定义
  pipeline.py          # run_pipeline(检索+生成,先 mock)
  seed.py              # 插入示例数据
scripts/dev.sh
data/eval.db           # SQLite 文件(gitignore)
.env / .env.example
tests/
docs/superpowers/
  specs/               # 本设计文档
  plans/               # 实施计划(后续生成)
```

## 数据模型(6 张表)

关系:

```
runs ──1:N──▶ traces ──1:N──▶ scores
  │                │
  │                └──1:N──▶ generations(一次 LLM 调用)
  └──1:1──▶ datasets ──1:N──▶ dataset_items
```

| 表 | 字段 | 说明 |
|---|---|---|
| datasets | id, name, description, created_at | 评测集 |
| dataset_items | id, dataset_id(FK), input, expected_output, bucket | 一条样本;expected_output=ground truth 要点;bucket=分桶标签 |
| runs | id, dataset_id(FK), status, config, created_at | 一次评测;status=running/done/failed;config=配置快照 JSON |
| traces | id, run_id(FK), dataset_item_id(FK), input, output, retrieved_context, latency_ms, created_at | 一次请求;retrieved_context=检索证据(忠实度要用) |
| generations | id, trace_id(FK), model, input_tokens, output_tokens, cost | 一次 LLM 调用 |
| scores | id, trace_id(FK), name, value, comment, created_at | 打分;name=指标名;value 可空 |

三个硬约束(面试必讲):
1. `scores.value` 可为 NULL——区分「0 分」和「没评上」(judge 挂了记 NULL 不记 0)。
2. `runs.config` 存 JSON 快照——对比「改提示词/换模型前后」时,得知道每轮当时什么配置。
3. `dataset_items.bucket`——分桶,别只报一个总分,要能定位到「哪个桶出了问题」。

## 接口契约

本章仅一个健康检查:

### GET /health

响应:

```json
{"status": "ok"}
```

业务接口(评测集 CRUD、run 流程)属第 2 章,本章不提供。

## 测试与验证

**TDD(pytest,先红后绿):**
- `models.py`:6 张表能建、外键关联正确
- 外键强制:插孤儿样本(dataset_id 不存在)断言抛 `IntegrityError`(验证 `PRAGMA foreign_keys=ON` 真在拦)
- `scores.value` 可空(插入 NULL 不报错)
- `seed.py`:插入后数据完整、关联正确

**验证(不调真实模型):**
- 跑 `seed.py` 后用 sqlite3/SQL 查:1 个 dataset、N 条 item、几条 trace、score 都在,且外键对得上
- `pipeline.run_pipeline("测试")` 返回结构正确(mock 数据)

## 本章不做

- run 生命周期(遍历评测集跑评测)——第 2 章
- evaluator(recall / faithfulness)——第 2 章
- 评测集 CRUD API——第 2 章
- 前端——第 3 章
- 真实检索管线(本章 mock,第 2 章换真的)
- 聚合与对比

## 关键决策记录

| 决策 | 选择 | 备选与理由 |
|---|---|---|
| 数据库 | SQLite | Postgres:数据量小(几十条评测集+几百次 run),零运维,1 个月别碰 Docker/MySQL |
| ORM | SQLAlchemy | 裸 sqlite3:和 MewHelp 一致,后续加字段/迁移省心 |
| 管线 | 先 mock | 直接接真实检索:先跑通「数据能存」这条流,管线第 2 章再换真的,别一上来卡在管线 |
| scores.value | 可空(NULL=没评上) | 0.0:区分「0 分」和「judge 挂了」,失败样本不污染分数 |
| runs.config | 存 JSON 快照 | 只存 config 引用:对比「改提示词前后」需要每轮当时的配置 |
| 密钥 | 本章不需要 | 管线 mock 不调真实模型;第 2 章接 judge 时再向用户要密钥 |
| SQLite 外键 | connect 事件开 `PRAGMA foreign_keys=ON` | SQLite 默认不强制外键,DDL 声明 `ForeignKey` 运行时也不拦;配反向测试(插孤儿样本断言 `IntegrityError`)保证真在拦 |
| 建表目录 | db.py 在建 engine 前自动 mkdir data/ | SQLite 不会自动建目录,相对路径 `data/eval.db` 目录不存在时连接直接 `unable to open database file` |
| 测试导包 | pytest 配 `pythonpath=["."]` | `uv init --bare` 建应用型项目,pytest 默认只把 `tests/` 加进 sys.path,找不到 `backend` 包 |
