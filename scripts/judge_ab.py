"""裁判 A/B 实验(Ch28):用另一个模型把**已存 run** 重新打一遍分,和原裁判对比。

为什么是「配对比较」而不是「重跑评测」:
  · 输入(问题/回答/检索证据)完全取自数据库里已存的 trace —— 两次打分看到的是**同一份东西**;
  · 所以分数差异**只能**来自裁判模型,不被「生成随机性」污染;
  · 也不用重跑被测系统,省时省钱。

调用方式(把裁判换成另一个 OpenAI 兼容模型):
    JUDGE_BASE_URL=... JUDGE_API_KEY=... JUDGE_MODEL=... \
        uv run python scripts/judge_ab.py <run_id>

**局限(必须说清)**:不同裁判的「判断能力」本来就不同,所以分数差异**不能**直接归因成
「原裁判偏袒自己」。能站得住的结论是:**裁判模型本身是个变量**——它和被测系统一样需要被验证。
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI  # noqa: E402

from backend import evaluators, llm  # noqa: E402
from backend.db import SessionLocal  # noqa: E402
from backend.models import DatasetItem, Score, Trace  # noqa: E402

JUDGE_FNS = {
    "faithfulness": lambda t, exp: evaluators.faithfulness(t.output, t.retrieved_context),
    "context_precision": lambda t, exp: evaluators.context_precision(t.input, t.retrieved_context),
    "context_recall": lambda t, exp: evaluators.context_recall(t.input, exp, t.retrieved_context),
    "answer_relevance": lambda t, exp: evaluators.answer_relevance(t.input, t.output),
    "answer_correctness": lambda t, exp: evaluators.answer_correctness(t.input, exp, t.output),
}


def install_judge_client(base_url: str, api_key: str, model: str) -> None:
    """把 evaluators 底层的 llm.chat_json 换成另一个模型。

    evaluators 里是 `from backend import llm` + `llm.chat_json(...)`,所以在这里替换
    llm.chat_json 就能换掉裁判——**prompt 模板、temperature、解析逻辑全都原样不变**,
    唯一的变量就是模型。这正是配对比较要的。
    """
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=60)

    def _chat_json(messages, temperature=0.0):
        # 必须和原 chat_json 一致地开 JSON mode —— 否则对比里混进了「有没有强制 JSON」
        # 这个变量,而我们要的是「只换模型」。原实现见 backend/llm.py:chat_json。
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = r.choices[0].message.content or ""
        try:
            return json.loads(content)   # 与原实现一致:解析失败返回 None
        except json.JSONDecodeError:
            return None

    llm.chat_json = _chat_json


def stored_scores(run_id: int) -> dict:
    s = SessionLocal()
    out = defaultdict(dict)
    for sc in s.query(Score).join(Trace, Score.trace_id == Trace.id).filter(Trace.run_id == run_id):
        out[sc.trace_id][sc.name] = sc.value
    s.close()
    return out


def main(run_id: int) -> None:
    s = SessionLocal()
    rows = (
        s.query(Trace, DatasetItem)
        .join(DatasetItem, Trace.dataset_item_id == DatasetItem.id)
        .filter(Trace.run_id == run_id)
        .all()
    )
    s.close()

    old = stored_scores(run_id)
    install_judge_client(
        os.environ["JUDGE_BASE_URL"], os.environ["JUDGE_API_KEY"], os.environ["JUDGE_MODEL"]
    )
    print(f"Run {run_id}: {len(rows)} 条样本,裁判 = {os.environ['JUDGE_MODEL']}\n")

    pairs = defaultdict(list)
    for t, it in rows:
        if it.bucket == "库外":
            continue  # 库外题只评拒答(机械指标),没有 LLM judge
        for name, fn in JUDGE_FNS.items():
            r = fn(t, it.expected_output)
            if r is None:
                # 不静默跳过:裁判返回 None = 调用失败或 JSON 解析失败,必须让人看见
                print(f"  [{t.input[:14]:16s}] {name:18s} ⚠ 裁判返回空(调用失败/解析失败)")
                continue
            a, b = old.get(t.id, {}).get(name), r["score"]
            pairs[name].append((a, b))
            print(f"  [{t.input[:14]:16s}] {name:18s} 原={a} 新={b} Δ={'' if a is None else f'{b-a:+.2f}'}")

    print(f"\n{'指标':22s}{'原裁判均':>10s}{'新裁判均':>10s}{'Δ':>9s}{'n':>5s}")
    print("-" * 58)
    for name, ps in pairs.items():
        valid = [(a, b) for a, b in ps if a is not None]
        if not valid:
            continue
        oa, nb = sum(a for a, _ in valid) / len(valid), sum(b for _, b in valid) / len(valid)
        print(f"{name:22s}{oa:>10.4f}{nb:>10.4f}{nb - oa:>+9.4f}{len(valid):>5d}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
