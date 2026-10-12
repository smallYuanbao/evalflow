# EvalFlow Ch21 设计:知识库地图性能修复

## 定位

不是新功能,是一次「用起来才发现」的性能修复。知识库页面首次进入接口超时、之后每次干等 35 秒。根因是请求里做了三件不该做的事:全表扫描、重算静态数据、同步阻塞。

## 现状(代码位置)

原 `knowledge_map` 端点([main.py](../../backend/main.py),现已抽到 [knowledge_map.py](../../backend/knowledge_map.py)):

```python
inputs = [it.input for it in s.query(DatasetItem).all()]  # 全表扫描
chunk_vecs = embed([k["text"] for k in KNOWLEDGE])        # 每次都重算静态知识库
query_pts = project(embed(inputs), mean, basis)           # 全部 input 一次性 embed
```

实测:`GET /knowledge/map` **35.0s**(23 条知识块 3.1s + 697 条样本 28.1s),embedding 超时 60s。

## 决策

### 决策 1:静态部分缓存(知识块 embedding / PCA 基底 / chunk 坐标)

知识库 [knowledge.py](../../backend/knowledge.py) 是写死的静态数据,chunk embedding、PCA 基底、chunk 坐标在进程生命周期内**不变**。首次计算后存模块级变量,后续请求共用。

**理由**:把「静态成本」从每次请求里拿掉。单进程 uvicorn 下所有请求共享;多 worker 每进程各算一次,可接受(demo 量级)。

### 决策 2:样本问题有界(去重 + 上限 100)

`_recent_unique_inputs(limit)`:按 `id` 倒序取近 `limit*3` 条候选,按 `input` 去重,截到 `limit`。

**理由**:地图是给人眼看散点的,100 个点和 700 个点看到的结论一样,但代价差 7 倍、且 700 个点会糊成一团。**有界查询**治本,清库只治标(dev 库与测试共库,样本仍会累积)。

### 决策 3:embedding 超时可配(默认 120s)

`config.py` 加 `embed_timeout: int = 120`,`embedding.py` 用它替代硬编码 60s。

**理由**:Ollama 冷启动要先把 bge-m3 载入内存,批量文本也要时间——60s 在「冷启动 + 大批量」时会误报超时。给足余量,并把旋钮交给 `.env`。

## 验收

- [x] `GET /knowledge/map` 从 35s 降到冷缓存 8s / 缓存命中 0.7s。
- [x] 知识块只嵌入一次(第二次调用不触发 embed)。
- [x] 样本问题去重 + 上限 100。
- [x] 现有 85 后端测试全绿 + 3 个新增。

## 本章不做

- 全库数据清理(测试与 dev 共库是历史遗留,单独议)。
- 把地图改成后台预计算 / 增量更新(有界 + 缓存已够 demo 量级)。
