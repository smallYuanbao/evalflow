"""评测集自检(Ch32):把「评测集写错了」这类静默失败挡在跑之前。

**为什么需要**:`recall` 是机械子串匹配——`expected_output` 里的要点只要**不是逐字**
出现在检索证据里,就判 0。「物理降温」和「温水擦浴」语义相同,但字面不同,分数天差地别。

后果是**静默的**:评测集写错了不会报错,只会让分数莫名偏低——
**你会以为是系统检索差,其实是评测集的措辞和知识库对不上**。
这和 Ch27「用自己的数据测自己的规则」是同一个病:错在尺子,怪在被测对象。

参考 MewHelp 的 `validate_eval_ch04.py`(300 题手写 ground truth「靠脚本兜住,不靠人眼」),
但适配 EvalFlow 的两种情况:
  · 结构检查 —— 纯数据层面,不需要跑过评测;
  · 证据检查 —— 拿**已经跑过的 run** 的检索证据比对要点(没有目标系统的知识库,
    就用「实际检索到了什么」代替)。
"""
import json
from collections import defaultdict

from backend.db import SessionLocal
from backend.models import DatasetItem, Trace

# 「库外」这个桶名是评分语义的开关(run_service 用它决定评不评 recall)。
# 从 run_service import 会拖进 celery 等重依赖,故在此重复一份并集中说明。
ABSENT_BUCKET = "库外"


def _points(expected_output: str) -> list[str]:
    """期望要点:用 / 切(与 evaluators.recall 同一套规则)。"""
    return [p.strip() for p in (expected_output or "").split("/") if p.strip()]


def _issue(level: str, rule: str, detail: str, item_id: int | None = None) -> dict:
    return {"level": level, "rule": rule, "item_id": item_id, "detail": detail}


def check_structure(items: list[DatasetItem]) -> list[dict]:
    """结构自检:不需要跑过评测,纯看数据本身合不合理。"""
    issues: list[dict] = []
    seen: dict[str, int] = defaultdict(int)

    for it in items:
        text = (it.input or "").strip()
        seen[text] += 1
        pts = _points(it.expected_output or "")
        bucket = (it.bucket or "").strip()

        # 1) 库内题没写要点 → recall 恒为 0,不是检索的问题
        if bucket != ABSENT_BUCKET and not pts:
            issues.append(_issue("error", "empty_expected_output",
                                 "库内题没有期望要点,recall/hit@k 恒为 0", it.id))

        # 2) 库外题带了要点 → 自相矛盾(库外只评拒答,不评 recall)
        if bucket == ABSENT_BUCKET and pts:
            issues.append(_issue("warning", "absent_bucket_with_points",
                                 "库外题带了期望要点,但它只评「拒答」,要点不会生效", it.id))

        # 3) 分桶为空 → 会被当成库内题用 recall+judge 评(见 run_service)
        if not bucket:
            issues.append(_issue("error", "empty_bucket",
                                 "分桶为空,该样本会被当成库内题评分(库外题将按错的方式评)", it.id))

        # 4) 要点里有空项(如 "a//b" 或首尾多余的 /)
        raw = it.expected_output or ""
        if raw.strip() and len(_points(raw)) != len([p for p in raw.split("/") if p.strip() != ""]):
            issues.append(_issue("warning", "malformed_points",
                                 f"期望要点里有空项(原文:{raw!r}),请检查 / 分隔", it.id))

    # 5) 同一评测集内问题重复 → 一条会被另一条覆盖或双计
    for text, n in seen.items():
        if text and n > 1:
            issues.append(_issue("warning", "duplicate_input",
                                 f"问题重复出现 {n} 次:{text[:30]}"))

    return issues


def check_against_run(items: list[DatasetItem], run_id: int) -> list[dict]:
    """证据自检:拿某个 run 实际检索到的证据,比对期望要点。

    只报「**所有要点一个都没命中**」的题——那强烈提示要点措辞与证据对不上
    (也可能是检索真差,所以定级为 warning,由人判断)。
    """
    s = SessionLocal()
    traces = s.query(Trace).filter(Trace.run_id == run_id).all()
    ctx_by_item = {t.dataset_item_id: (t.retrieved_context or "") for t in traces}
    s.close()

    issues: list[dict] = []
    checked = hit_any = 0
    for it in items:
        if (it.bucket or "").strip() == ABSENT_BUCKET:
            continue
        ctx = ctx_by_item.get(it.id)
        if ctx is None:      # 这个 run 里没有这条样本
            continue
        pts = _points(it.expected_output or "")
        if not pts:
            continue
        checked += 1
        if any(p in ctx for p in pts):
            hit_any += 1
        else:
            issues.append(_issue(
                "warning", "points_not_in_evidence",
                f"全部 {len(pts)} 个要点都没在检索证据里逐字出现(要点:{'/'.join(pts)[:40]})"
                "—— 可能是要点措辞与知识库不一致(评测集问题),也可能检索确实没找到",
                it.id))

    if checked:
        issues.append(_issue(
            "info", "evidence_summary",
            f"该 run 覆盖 {checked} 条库内题,其中 {hit_any} 条的要点能在证据里命中"
            f"({hit_any / checked:.0%} 命中率)"))
    return issues


def validate_dataset(dataset_id: int, run_id: int | None = None) -> dict:
    s = SessionLocal()
    items = s.query(DatasetItem).filter(DatasetItem.dataset_id == dataset_id).all()
    s.close()

    issues = check_structure(items)
    if run_id is not None:
        issues += check_against_run(items, run_id)

    errors = sum(1 for i in issues if i["level"] == "error")
    warnings = sum(1 for i in issues if i["level"] == "warning")
    return {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "item_count": len(items),
        "summary": {"errors": errors, "warnings": warnings, "total": len(issues)},
        "issues": issues,
    }
