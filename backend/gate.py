"""回归门禁(Ch15):对一次 run 的聚合指标套规则,给出 PASS/FAIL。

纯函数、读时计算、不落库——门禁是「对已有指标的视图」而非新状态。
规则 = 绝对下限(min)+ 相对基线的最大允许回退(max_regression),两条腿 AND。
门禁对象只挑 5 个 LLM judge 指标;recall(机械关键词)/ rejection(拒答率,非质量地板)不门禁。
"""

GATE_RULES: dict[str, dict[str, float]] = {
    "faithfulness": {"min": 0.7, "max_regression": 0.05},
    "context_precision": {"min": 0.7, "max_regression": 0.05},
    "context_recall": {"min": 0.7, "max_regression": 0.05},
    "answer_relevance": {"min": 0.7, "max_regression": 0.05},
    "answer_correctness": {"min": 0.7, "max_regression": 0.05},
}


def evaluate_gate(
    scores: dict[str, float | None],
    baseline_scores: dict[str, float | None] | None = None,
) -> dict:
    """对聚合后的 per-metric 均值做门禁判定。

    scores: 被门禁 run 的 {metric: avg|null};baseline_scores: 基线 run 同结构(可选)。
    返回 {passed, checks};checks 逐指标带当前值/阈值/基线值/变化/通过与否/备注。
    null 指标(judge 挂)记未评且不通过——门禁的门槛是「每个被门禁指标都评上且达标」。
    """
    checks = []
    for metric, rule in GATE_RULES.items():
        value = scores.get(metric)
        threshold = rule["min"]
        tolerance = rule["max_regression"]

        baseline_value = None
        delta = None
        if baseline_scores is not None:
            baseline_value = baseline_scores.get(metric)
            if value is not None and baseline_value is not None:
                delta = round(value - baseline_value, 4)

        if value is None:
            passed, note = False, "未评"
        else:
            over_min = value >= threshold
            over_baseline = True
            if baseline_value is not None:
                over_baseline = value >= baseline_value - tolerance
            passed = over_min and over_baseline
            if passed:
                note = None
            elif not over_min and not over_baseline:
                note = "低于阈值,且较基线下降"
            elif not over_min:
                note = "低于阈值"
            else:
                note = "较基线下降超过容忍度"

        checks.append({
            "metric": metric,
            "value": value,
            "threshold": threshold,
            "baseline_value": baseline_value,
            "delta": delta,
            "passed": passed,
            "note": note,
        })

    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
    }
