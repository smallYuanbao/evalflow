# 指标注册表:指标 key 的展示顺序(检索 → 生成 → 库外)。
# 加指标 = 这里加一行 + run_service 加一个 judge 调用 + 前端标签映射加一行。
METRIC_ORDER = [
    "recall",
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevance",
    "answer_correctness",
    "rejection",
]
