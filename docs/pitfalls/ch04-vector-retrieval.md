# Ch04 踩坑:向量检索(Ollama + ChromaDB)

> 这一章把关键词检索换成真正的 embedding 向量检索(bge-m3 + ChromaDB)。坑在「依赖版本」和「向量库默认值」上。

## 坑 1:onnxruntime 必须按架构 pin 版本

**现象**:装 `chromadb` 时,它拉进来的 `onnxruntime` 装不上/装错版本。

**根因**:chromadb 依赖 onnxruntime;而 `onnxruntime>=1.24` 已经**没有 Intel Mac(x86_64)的 wheel**,直接装会失败或装上不兼容版本。

**修法**:显式 pin 到有 wheel 的版本:

```bash
uv add chromadb numpy requests "onnxruntime==1.23.2"
```

**原理**:带**原生二进制**的库(onnxruntime、numpy、pydantic-core 等)要区分 CPU 架构和平台。Mac 分 Intel(x86_64)和 Apple Silicon(arm64),新版本可能不再为老架构发 wheel。**装依赖报「找不到 wheel / 编译失败」,先看是不是架构问题 + 版本 pin**。

## 坑 2:ChromaDB 默认 L2 距离,不是余弦

**现象**:检索出来的结果和预期相似度排序不符,「距离越小越相似」的语义也不对。

**根因**:ChromaDB 建 collection 时**默认距离度量是 L2(欧氏距离)**,而本项目要的是**余弦相似度**(embedding 语义相似常用 cosine)。

**修法**:建 collection 时显式指定 `metadata={"hnsw:space": "cosine"}`。

**原理**:向量库的距离度量不能靠默认——L2、cosine、内积(IP)三种语义差别很大,取决于你的 embedding 是怎么训的、怎么用的。**embedding 用哪个模型,就去查它官方推荐的距离度量**,一般 sentence/embedding 模型配 cosine。

## 坑 3:embedding 依赖本地 Ollama,要先起服务

**现象**:调检索时报连接 `localhost:11434` 失败。

**根因**:embedding 走本地 Ollama 的 `bge-m3` 模型,没起 `ollama serve` 就调不通。

**修法**:先 `ollama serve`(后台常驻),`ollama list` 能连上、且已 `ollama pull bge-m3` 才算就绪。

**原理**:本地 embedding/LLM 是一层**外部依赖**,和数据库一样要在跑之前确认「服务在不在、模型在不在」。联调时「代码没变却突然失败」,先查依赖服务有没有起。
