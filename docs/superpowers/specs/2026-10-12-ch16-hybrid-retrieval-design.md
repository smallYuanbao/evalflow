# EvalFlow Ch16 设计:混合检索(dense + BM25 + RRF)

## 定位

Ch04 的检索是「纯向量 dense」——query 嵌入后按余弦 top-k。它擅长**语义相近**,但会漏掉**关键词精确匹配**(商品名、编号、生僻词、专业术语这类「字面必须对上」的情况)。

Ch16 加**混合检索(hybrid retrieval)**:dense(语义)+ sparse(关键词)两路融合,各取所长。这是 RAG 生产化的第一块硬骨头,也是 Ch17 复盘里「用门禁验证改进」的被测对象。

## 现状(代码位置)

| 能力 | 位置 | 状态 |
|---|---|---|
| 纯 dense 检索 | [retriever.py](../backend/retriever.py) `retrieve`(chroma 余弦 top-k) | 已有 |
| 知识库 | [knowledge.py](../backend/knowledge.py) `KNOWLEDGE`(23 条 chunk,含 id/text/category) | 已有 |
| embedding | [embedding.py](../backend/embedding.py) Ollama `bge-m3`(只取 dense 一路) | 已有 |
| 检索调用链 | [pipeline.py](../backend/pipeline.py) `run_pipeline` → `retrieve` | 已有 |
| 关键词/sparse 一路 | —— | **缺** |
| 检索方式进快照(可复现/A-B) | [snapshot.py](../backend/snapshot.py) | **缺** |

## 决策

### 决策 1:sparse 用「应用层手写 BM25」,不换库

dense 仍走 chroma;sparse 用**手写 BM25**(对 `KNOWLEDGE` 内存建倒排索引),两路在应用层融合。**不迁移 Milvus**(用户已确认)。

**理由**:BM25 是「词频 + 逆文档频率」的经典关键词打分,几十行就能写清楚;「关键词那一半」不依赖向量库。换 Milvus 是「生产级选型」的部署升级,与本概念的落地无关,留作后续薄换(接口 `hybrid_retrieve` 不变)。

### 决策 2:BM25 手写 + 字符二元组分词,不引 jieba

手写标准 BM25(k1=1.5, b=0.75),分词用**字符二元组(bigram)**——中文无空格,bigram 能捕获「发烧」「湿疹」这类双字关键词的精确命中。

**理由**:手写是为把公式讲透(这是学习项目);bigram 零依赖且小语料够用。**放弃** jieba(生产中文分词标准答案,但引入依赖 + Dockerfile 改动,超出本章「讲清 dense/sparse 概念」的范围,生产化再上)。

### 决策 3:融合用 RRF(倒数排名融合),k=60

两路各取 top-k,按**排名**贡献 `1/(k+rank)`,累加后重排取 top-k。

**理由**:RRF 是**尺度无关**的——dense 的余弦(0~1)和 BM25(无上界)分数不能直接相加,但「排名」可以。RRF 免去归一化,是混合检索的事实标准融合法。

### 决策 4:retrieval 作为 run 配置(dense|hybrid),默认 hybrid,写进 Ch09 快照

`Run.config` 快照新增 `retrieval` 字段,取值 `hybrid`(默认)/ `dense`。发起评测时可选,`run_pipeline` 按它分发。

**理由**:这是 Ch17「eval-driven development」的伏笔——**先跑一版 dense 基线,再跑 hybrid,用 Ch15 门禁证明「混合检索有没有把指标拉上去」**。不写进快照就没法复现「这次用哪种检索跑出来的」。

### 决策 5:前端暴露检索方式

- RunsView 加「检索方式」下拉(dense/hybrid),发起评测时随 `top_k` 一起进 config。
- RunDetailView「复现上下文」卡加一行「检索方式」。
- 逐条明细的命中标签从「相似度」改「融合分」(score 现在是 RRF 值,不再是余弦相似度)。

## 验收

- [x] BM25:关键词命中的 chunk 排最前(如 query「发烧」→ fever-* 排前)。
- [x] hybrid 融合:同时被 dense 和 sparse 命中的 chunk 排最前(RRF 累加)。
- [x] `retrieval` 进快照,dense/hybrid 两种模式可切换且结果可复现。
- [x] 现有 72 后端测试全绿(65 旧 + 7 新增 bm25/hybrid/retrieval)。

## 本章不做(超出范围)

- 换 Milvus / Qdrant(生产级向量库选型,后续薄换)。
- rerank 模型(cross-encoder 精排)——这是「混合检索之后的第二块」,单独成章。
- 分块策略/重叠调优(要动知识库内容,和评测指标耦合,另议)。
- jieba 分词(生产化再上)。
