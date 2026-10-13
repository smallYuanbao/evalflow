# EvalFlow

**一个 RAG / LLM 评测平台。** 造评测集 → 跑评测 → 看指标 → 对比配置 → 判「能不能上线」。

它真正的价值不在于「算出分数」——那任何人写个脚本都能做。而在于让分数
**可比、可信、可行动**：可复现的快照、经过校准的 judge、能定位到具体样本的门禁与归因。

> **它评测的对象后来换成了我自己做的另一个 RAG 应用(baby-ai)。**
> 接上真实系统后，并发评测**逼出了对方一个潜伏的并发 bug**，评测平台**自己也被发现有指标判错**。
>
> 📖 **[完整复盘 → docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md)**（为什么这么做、踩过什么、面试怎么讲）

---

## 能做什么

- **评测集管理**:问题 + 期望要点 + 分桶(库内/库外)
- **评测执行**:Celery 队列 + 并发;支持本地 toy pipeline 或**外部真实 RAG 应用**
- **指标**:
  - 机械指标(不调 LLM):recall、命中@k、MRR、拒答率
  - LLM-as-Judge:忠实度、上下文精度/召回、答案相关性/正确性(多次采样取均值 + 方差)
- **Judge 校准**:人工标金标准 → 出 bias / MAE / Pearson
- **回归门禁**:阈值 + 基线回归 → PASS/FAIL
- **归因与对比**:分桶归因、逐条 Diff、模型性价比、历史趋势
- **可复现**:run 快照记录知识库/prompt/模型/数据集,**以及外部被测系统的状态**
- **导出**:流式 CSV(样本量不受内存限制)

---

## 快速开始

**依赖**:Python 3.12、Node 20、Redis、[Ollama](https://ollama.com)(嵌入模型 `bge-m3`)、Docker(可选)
**需要**:`.env` 里填 `CHAT_API_KEY` / `CHAT_BASE_URL` / `CHAT_MODEL`(参考 `.env.example`)

```bash
# Redis(Celery broker)
docker run -d --name evalflow-redis -p 6379:6379 redis:7-alpine

# 后端
uv sync
uv run uvicorn backend.main:app --port 8000

# 评测 worker(另开一个终端)
uv run celery -A backend.celery_app worker --pool=threads --concurrency=4 --loglevel=info

# 前端(另开一个终端)
cd frontend && npm install && npm run dev     # → http://localhost:5173

# 造一份示例评测集(可选)
uv run python -c "from backend.seed import seed; seed()"
```

浏览器打开 <http://localhost:5173>。

**一键部署**:`cp .env.example .env`(填好)→ `docker compose up --build`

---

## 评测一个外部 RAG 应用

不评自己的 pipeline，而是评真实系统(见 [Ch26 spec](docs/superpowers/specs/2026-10-13-ch26-evaluate-babyai-design.md)):

```bash
EVAL_TARGET=babyai BABYAI_BASE_URL=http://localhost:3001 uv run uvicorn backend.main:app --port 8000
```

被测系统只要暴露两个接口:

- `POST /api/chat` → `{answer, references: [{id, text}]}`
- `GET  /api/meta` → 自身状态(版本/模型/检索配置/知识库规模)，供快照记录

> 第二个接口是可复现性的关键:可复现性有一半在**对方系统**里。拿不到时快照会显式标记
> 「本次结果不可与历史对比」,而不是静默记空。

---

## 架构

```
浏览器 ──▶ FastAPI 后端 ──▶ Celery 队列 ──▶ worker
              │  ▲                              │
              │  └──────── Redis ───────────────┘
              ▼                       ▼
          SQLite/PG              检索 + 生成 + 打分
        (评测集/run/score)               │
                                    ┌────┴────┐
                                 Chroma    Ollama(嵌入)
                                    │
                              或 HTTP 调外部 RAG 应用
```

**技术栈**:FastAPI · SQLAlchemy + alembic · Celery + Redis · React 18 + Vite + TS + antd · Playwright

---

## 文档导航

| 文档 | 内容 |
|---|---|
| **[docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md)** | **复盘与面试叙事**——先看这个 |
| [docs/pitfalls/](docs/pitfalls/index.md) | 16 份踩坑记录，按「现象 → 根因 → 修法 → 原理」 |
| [docs/superpowers/specs/](docs/superpowers/specs/) | 各章设计文档(决策 + 取舍) |
| [docs/superpowers/plans/](docs/superpowers/plans/) | 各章实施计划(Task 列表) |

> **关于这套文档结构**:每章都是「先写 spec(决策 + 为什么)→ 再写 plan(Task 清单)→ 实施 →
> 同步回文档」。这是我做所有项目的固定流程，`docs/superpowers/` 就是它的产物。

---

## 测试

```bash
uv run pytest -q                       # 后端(92)
cd frontend && npm test                # 前端单测(33)
cd frontend && npx playwright test     # 端到端(主流程)
```

CI 工作流见 `.github/workflows/ci.yml`(pytest / vitest / build / e2e 四 job)。
