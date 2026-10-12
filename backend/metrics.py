# 指标注册表:指标 key 的展示顺序(检索 → 生成 → 库外)。
# 加指标 = 这里加一行 + run_service 加一个 judge 调用 + 前端标签映射加一行。
METRIC_ORDER = [
    "recall",
    "hit_at_k",
    "mrr",
    "context_precision",
    "context_recall",
    "faithfulness",
    "answer_relevance",
    "answer_correctness",
    "rejection",
]

# 指标 key → 中文列名(CSV 导出用)。这份要和前端 src/utils/metrics.ts 的 METRIC_LABELS 保持一致:
# 两份分别服务「后端产出物」和「前端界面」,不好共用,靠这条注释提醒同步(Ch24)。
METRIC_LABELS = {
    "recall": "召回(机械)",
    "hit_at_k": "命中@k",
    "mrr": "MRR",
    "context_precision": "上下文精度",
    "context_recall": "上下文召回",
    "faithfulness": "忠实度",
    "answer_relevance": "答案相关性",
    "answer_correctness": "答案正确性",
    "rejection": "拒答率",
}
