"""回归门禁(Ch15):对一次 run 的聚合指标套规则,给出 PASS/FAIL。

纯函数、读时计算、不落库——门禁是「对已有指标的视图」而非新状态。
规则 = 绝对下限(min)+ 相对基线的最大允许回退(max_regression),两条腿 AND。
门禁对象只挑 5 个 LLM judge 指标;recall(机械关键词)/ rejection(拒答率,非质量地板)不门禁。
"""

# —— 门禁阈值(Ch28 校准,不是拍的)——
#
# 来源:`scripts/calibrate_gate.py` + `scripts/judge_ab.py`,被测系统 baby-ai
#       (dataset 3,run 12/13/14 同配置重跑 + 换裁判重打)。
#
# **max_regression 的量法**:门禁比的是两次 run,而每次 run 都会重新生成回答、裁判也可能换。
# 所以容忍度必须**大于「什么都没改时的自然波动」**,否则天天误报。实测三块噪声:
#
#   | 指标              | 生成随机 | 跨裁判 | 自复现 | 取用 |
#   |-------------------|---------|--------|--------|------|
#   | faithfulness      | 0.072   | 0.053  | ~0     | 生成侧主导 |
#   | context_precision | 0.024   | 0.224  | 0.007  | 裁判主导 |
#   | context_recall    | 0.000   | 0.313  | ~0     | 裁判主导 |
#   | answer_relevance  | 0.134   | 0.022  | 0.002  | 生成侧主导 |
#   | answer_correctness| 0.181   | 0.041  | 0.001  | 生成侧主导 |
#
# **下面取的是「裁判固定」那一列的 ×1.3 安全系数**——因为 EvalFlow 的裁判就是固定的
# (chat_model 已写进 run 快照)。换裁判会让上下文侧指标的噪声涨 10 倍以上,那时必须重校。
#
# **min 的性质要说清**:它来自「健康系统的低位」,挡的是**比我平时差**(自我一致性),
# 不是**质量不合格**。真正的质量下限需要人工标注「什么不可接受」——那是另一套工作。
#
# ⚠ **换被测系统必须重校**:这些值绑在 baby-ai 的实际水平上(faithfulness 基线只有 0.16)。
#    换个系统直接套用,会得到「永远红灯」或「永远绿灯」。
GATE_RULES: dict[str, dict[str, float]] = {
    "faithfulness": {"min": 0.066, "max_regression": 0.094},
    "context_precision": {"min": 0.354, "max_regression": 0.031},
    "context_recall": {"min": 0.459, "max_regression": 0.020},
    "answer_relevance": {"min": 0.394, "max_regression": 0.174},
    "answer_correctness": {"min": 0.239, "max_regression": 0.235},
}


# 覆盖率下限:该指标实际评上的样本占比低于它就**不给判定**。
# 理由:20 条里挂了 17 条 judge,均值只由剩下 3 条算出来——那是个「看起来正常」的数字,
# 却基于 15% 的样本。门禁宁可说「样本不足」,也不该拿它去和基线比。
MIN_COVERAGE = 0.8


def evaluate_gate(
    scores: dict[str, float | None],
    baseline_scores: dict[str, float | None] | None = None,
    coverage: dict[str, dict[str, int]] | None = None,
) -> dict:
    """对聚合后的 per-metric 均值做门禁判定。

    scores: 被门禁 run 的 {metric: avg|null};baseline_scores: 基线 run 同结构(可选);
    coverage: {metric: {scored, attempted}}(可选,来自 aggregate_run 的 score_coverage)。
    返回 {passed, checks};checks 逐指标带当前值/阈值/基线值/变化/通过与否/备注。

    不通过有三种原因,分清楚很重要:
      · 未评     —— 一条都没评上
      · 样本不足 —— 评上的比例低于 MIN_COVERAGE(均值不可信)
      · 低于阈值 / 较基线下降 —— 真的质量信号
    """
    checks = []
    for metric, rule in GATE_RULES.items():
        value = scores.get(metric)
        threshold = rule["min"]
        tolerance = rule["max_regression"]

        cov = (coverage or {}).get(metric)
        if cov and cov.get("attempted"):
            ratio = cov["scored"] / cov["attempted"]
            if ratio < MIN_COVERAGE:
                checks.append({
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "baseline_value": (baseline_scores or {}).get(metric),
                    "delta": None,
                    "passed": False,
                    "note": f"样本不足({cov['scored']}/{cov['attempted']} 评上,均值不可信)",
                })
                continue

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
