# EvalFlow 设计与计划索引

> 这个目录记录**每一章为什么这么做、怎么做**。31 章，每章两份文档。

## 结构

```
specs/   「为什么」—— 决策 + 取舍(每章的 design spec)
plans/   「怎么做」—— Task 列表 + checkbox(每章的实施计划)
```

**工作流**:先写 spec(定决策、写明放弃什么)→ 再写 plan(拆 Task)→ 实施 → **同步回这两份文档**。
从 Ch01 到 Ch31 没变过。这也是我做所有项目的固定流程。

**命名**:`<日期>-ch<N>-<slug>-design.md`(spec) / `<日期>-ch<N>-<slug>.md`(plan)。

---

## 按性质分组

> 目录结构是「规格 vs 计划」的二分,但**章节本身的性质在中途变了**——
> 前期是「建一个新能力」,后期转向「建的这东西可信吗」。分组如下,这个转折本身就是一条线索。

### 一、功能设计(21 章)——「建一个新能力」

| 章 | 做了什么 |
|---|---|
| [Ch01](specs/2026-10-08-ch01-data-foundation-design.md) | 数据地基:SQLite 建表、外键、NULL 语义 |
| [Ch02](specs/2026-10-08-ch02-evaluation-run-design.md) | 评测主流程:检索 → 生成 → 打分 |
| [Ch03](specs/2026-10-08-ch03-frontend-design.md) | 前端:React + antd,跑通最小闭环 |
| [Ch04](specs/2026-10-08-ch04-vector-retrieval-design.md) | 向量检索:chroma + Ollama 嵌入 |
| [Ch05](specs/2026-10-09-ch05-metrics-deepening-design.md) | 指标深化:分桶聚合、指标注册表 |
| [Ch06](specs/2026-10-09-ch06-run-comparison-design.md) | 多 run 对比 |
| [Ch07](specs/2026-10-09-ch07-frontend-enhancement-design.md) | 前端增强:路由懒加载、图表 |
| [Ch08](specs/2026-10-09-ch08-deployment-design.md) | Docker 一键部署 |
| [Ch09](specs/2026-10-09-ch09-reproducibility-design.md) | **可复现**:run 快照(知识库/prompt/模型/数据集哈希) |
| [Ch10](specs/2026-10-10-ch10-task-queue-design.md) | 任务队列化:Celery + 并发 + 进度 |
| [Ch11](specs/2026-10-10-ch11-llm-reliability-design.md) | LLM 可靠性:重试 + 熔断 + judge 校准 |
| [Ch12](specs/2026-10-10-ch12-security-cost-design.md) | 鉴权 + 限流 + 费用统计 |
| [Ch13](specs/2026-10-10-ch13-observability-design.md) | 结构化日志 + 指标趋势 + CSV 导出 |
| [Ch14](specs/2026-10-11-ch14-data-delivery-design.md) | PostgreSQL 可切换 + alembic + CI + e2e + HTTPS |
| [Ch15](specs/2026-10-12-ch15-regression-gating-design.md) | **回归门禁**:阈值 + 基线回归 → PASS/FAIL |
| [Ch16](specs/2026-10-12-ch16-hybrid-retrieval-design.md) | 混合检索:BM25 + RRF 融合 |
| [Ch18](specs/2026-10-12-ch18-explainability-calibration-design.md) | 可解释性(reason 下钻)+ Judge 校准机制 |
| [Ch19](specs/2026-10-12-ch19-bucket-attribution-model-compare-design.md) | 分桶归因 + 模型性价比 |
| [Ch20](specs/2026-10-12-ch20-metrics-refinement-design.md) | hit@k/MRR + 一键复跑 + judge 方差 |
| [Ch26](specs/2026-10-13-ch26-evaluate-babyai-design.md) | **评测真实 RAG 应用** + 跨系统可复现 |
| [Ch30](specs/2026-10-14-ch30-judge-configurable-design.md) | 裁判可独立配置(生成与裁判解耦) |

### 二、缺陷修复(7 章)——「修一个具体问题」

| 章 | 修了什么 |
|---|---|
| [Ch21](specs/2026-10-12-ch21-knowledge-map-perf-design.md) | 知识库地图 35s → 0.7s(全表扫描 + 无缓存) |
| [Ch22](specs/2026-10-12-ch22-usability-test-isolation-design.md) | 测试污染 dev 库 + 趋势/散点可读性 |
| [Ch23](specs/2026-10-12-ch23-input-guards-ux-design.md) | 输入防呆(后端 clamp)+ 中文 locale + 布局 |
| [Ch24](specs/2026-10-12-ch24-interaction-refinement-design.md) | 分桶必选 / 基线标签 / 金标准可清空 / 标签释义 |
| [Ch25](specs/2026-10-12-ch25-streaming-export-design.md) | 导出改流式(两端不再缓冲整份文件) |
| [Ch27](specs/2026-10-13-ch27-rejection-heuristic-design.md) | 拒答词表匹配不上真实系统的措辞 |
| [Ch29](specs/2026-10-14-ch29-comparability-design.md) | 门禁/归因/Diff 校验「两次是不是同一批题」 |

### 三、测量与校准(2 章)——「产出数据和结论,不是功能」

| 章 | 量了什么 |
|---|---|
| [Ch28](specs/2026-10-13-ch28-judge-variance-design.md) | 三个噪声源(生成/跨裁判/自复现)→ **据实校准门禁阈值** |
| [Ch31](specs/2026-10-14-ch31-coverage-and-calibration-design.md) | 指标覆盖率 + **第一次真正的人工校准**(16 条金标准 → bias/MAE/corr) |

### 四、规划与叙事(2 份)

| 文档 | 是什么 |
|---|---|
| [路线图](2026-10-09-roadmap-production-hardening.md) | Ch09–Ch14 的整体规划。**不是章节设计**,所以放在本目录顶层而非 `specs/` |
| [Ch17](specs/2026-10-12-ch17-retrospective-design.md) | 差距分析 + 复盘叙事(叙事正文在 [RETROSPECTIVE.md](../RETROSPECTIVE.md)) |

---

## 两个转折点

**Ch26 —— 从「建」转向「验」。**
在那之前,问题都在功能/界面层;接上真实 RAG 应用之后,问题开始指向**评测方法本身**。
Ch27–Ch31 全部在回答同一个问题:**这个数字凭什么可信**。

**Ch28 —— 从「改代码」转向「做测量」。**
这一章没改任何功能,产出是三组实测数据和一组校准阈值。
之后的 Ch31 更进一步:亲自动手标 16 条金标准,验证「尺子准不准」。

> 想知道「为什么会有这些章节」,看 [RETROSPECTIVE.md](../RETROSPECTIVE.md) 第五节。
> 想知道「踩过什么坑」,看 [docs/pitfalls/](../pitfalls/index.md)。
