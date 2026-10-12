"""知识库地图(Ch04):知识块 PCA 降到 2D,样本问题投影到同一坐标系。

Ch21 性能修复——原实现每次请求都 (a) 全表扫描所有样本、(b) 重新嵌入整个知识库,
在样本累积后接口要 30s+ 并偶发超时。两处根因:
  1. 知识库是静态的 → chunk embedding 与 PCA 基底只算一次并缓存;
  2. 地图是给人眼看散点的 → 样本问题有界(去重 + 上限),既快又看得清。
"""
from backend.db import SessionLocal
from backend.embedding import embed
from backend.knowledge import KNOWLEDGE
from backend.models import DatasetItem
from backend.pca import fit_pca, project

# 样本点上限:散点图是给人看的,上百个点已经足够,几百个既慢又糊成一团
MAX_QUERY_POINTS = 100

# 静态部分缓存:知识库(chunk embedding / PCA 基底 / chunk 坐标)不随请求变化,只算一次。
# 进程级缓存:单进程 uvicorn 下所有请求共用;多 worker 时每个进程各算一次,可接受。
_chunk_cache: dict | None = None


def _chunk_layout() -> dict:
    global _chunk_cache  # 函数内赋值必须声明 global,否则 _chunk_cache 被当成局部变量
    if _chunk_cache is None:
        vecs = embed([k["text"] for k in KNOWLEDGE])
        mean, basis = fit_pca(vecs)
        _chunk_cache = {"mean": mean, "basis": basis, "pts": project(vecs, mean, basis)}
    return _chunk_cache


def _recent_unique_inputs(limit: int) -> list[dict]:
    """取最近的去重样本问题(有界):返回 [{input, bucket}]。

    多取 3 倍候选,按 input 去重后截到 limit。带上 bucket 是为了能在散点图上看出
    「库外题是不是都聚在向量空间边缘」——这正是知识库地图的用法之一(Ch23)。
    """
    s = SessionLocal()
    try:
        rows = (s.query(DatasetItem.input, DatasetItem.bucket)
                .order_by(DatasetItem.id.desc())
                .limit(limit * 3)
                .all())
    finally:
        s.close()

    seen: set[str] = set()
    out: list[dict] = []
    for text, bucket in rows:
        if text and text not in seen:
            seen.add(text)
            out.append({"input": text, "bucket": bucket or "未分桶"})
            if len(out) >= limit:
                break
    return out


def knowledge_map() -> dict:
    """返回 {chunks, queries}:知识块与样本问题在同一 2D PCA 坐标系中的位置。"""
    layout = _chunk_layout()
    chunks = [
        {"id": k["id"], "text": k["text"], "category": k["category"],
         "x": round(layout["pts"][i][0], 4), "y": round(layout["pts"][i][1], 4)}
        for i, k in enumerate(KNOWLEDGE)
    ]

    inputs = _recent_unique_inputs(MAX_QUERY_POINTS)
    if inputs:
        pts = project(embed([q["input"] for q in inputs]), layout["mean"], layout["basis"])
        queries = [{"input": inputs[j]["input"], "bucket": inputs[j]["bucket"],
                    "x": round(pts[j][0], 4), "y": round(pts[j][1], 4)}
                   for j in range(len(inputs))]
    else:
        queries = []
    return {"chunks": chunks, "queries": queries}
