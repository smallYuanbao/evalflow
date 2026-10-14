"""Ch32:评测集自检——把「评测集写错了」这类静默失败挡在跑之前。"""
from backend.dataset_check import check_structure, validate_dataset
from backend.db import SessionLocal, init_db
from backend.models import Dataset, DatasetItem, Run, Trace


class _Item:
    """轻量替身:自检只看 input/expected_output/bucket 三个字段,不需要真 ORM。"""
    def __init__(self, i, inp, exp, bucket):
        self.id, self.input, self.expected_output, self.bucket = i, inp, exp, bucket


def test_structure_flags_empty_points_on_inbucket():
    """库内题没写要点 → recall 恒为 0,不是检索的问题。"""
    issues = check_structure([_Item(1, "宝宝发烧怎么办", "", "护理")])
    assert any(i["rule"] == "empty_expected_output" and i["level"] == "error" for i in issues)


def test_structure_flags_empty_bucket():
    """分桶为空 → 库外题会被当成库内题评(评分方式就错了)。"""
    issues = check_structure([_Item(1, "如何换轮胎", "", "")])
    assert any(i["rule"] == "empty_bucket" and i["level"] == "error" for i in issues)


def test_structure_flags_absent_bucket_with_points():
    """库外题带要点 → 自相矛盾(库外只评拒答,要点不生效)。"""
    issues = check_structure([_Item(1, "如何换轮胎", "找师傅", "库外")])
    assert any(i["rule"] == "absent_bucket_with_points" for i in issues)


def test_structure_flags_duplicate_input():
    issues = check_structure([_Item(1, "宝宝发烧怎么办", "a", "护理"),
                              _Item(2, "宝宝发烧怎么办", "b", "护理")])
    assert any(i["rule"] == "duplicate_input" for i in issues)


def test_structure_passes_clean_dataset():
    """干净的评测集不该报任何问题——别把正常情况也标红。"""
    issues = check_structure([
        _Item(1, "宝宝发烧怎么办", "物理降温/就医", "护理"),
        _Item(2, "如何换轮胎", "", "库外"),
    ])
    assert issues == []


def test_evidence_check_flags_points_never_hit():
    """证据自检:全部要点都没在检索证据里逐字出现 → 提示措辞可能对不上。

    这正是 EvalFlow 版的「要点写得再对、只要库里不是这么写的,分数就永远上不去」。
    """
    init_db()
    s = SessionLocal()
    ds = Dataset(name="chk", description="")
    s.add(ds)
    s.flush()
    # 要点是「拍嗝」,但证据里写的是「打出奶嗝」——子串匹配对不上
    it = DatasetItem(dataset_id=ds.id, input="宝宝吐奶怎么办",
                     expected_output="拍嗝/竖抱", bucket="护理")
    s.add(it)
    s.flush()
    run = Run(dataset_id=ds.id, status="done", config="{}")
    s.add(run)
    s.flush()
    s.add(Trace(run_id=run.id, dataset_item_id=it.id, input="宝宝吐奶怎么办",
                output="o", retrieved_context="吃完奶后将宝宝坚起来,轻轻拍后背让他打出奶嗝"))
    s.commit()
    did, rid = ds.id, run.id
    s.close()

    d = validate_dataset(did, run_id=rid)
    assert any(i["rule"] == "points_not_in_evidence" for i in d["issues"])
    # 同时给出总体命中率,便于判断是「个别题」还是「整体对不上」
    assert any(i["rule"] == "evidence_summary" for i in d["issues"])
