"""把人工标注的 CSV 写回 `DatasetItem.gold_scores`。

## 为什么需要脚本

`PUT /datasets/{id}/items/{item_id}/gold` 一次只能写一条，15 条手点容易漏/写错；
而且标注是在 CSV 里完成的，需要一条可复现的写入路径。

## CSV 格式

必需列：`item_id` + 五个指标（`faithfulness` / `context_precision` /
`context_recall` / `answer_relevance` / `answer_correctness`）。
可选列：`annotated_on_run`（记录 gold 是对着哪次 run 的输出标的）、`note`。

- 分数必须在 [0, 1]；留空表示「这条不标该指标」，校准时会跳过。
- 每行至少要有一个分数。

## 用法

    # 先检查，不写库
    .venv/bin/python scripts/import_gold.py docs/reports/xxx.csv --dataset-id 4 --dry-run

    # 正式写入（自动备份被覆盖的旧 gold）
    .venv/bin/python scripts/import_gold.py docs/reports/xxx.csv --dataset-id 4

## 注意

gold 是**独立于 judge 的人工判断**。不要拿 judge 的输出回填——那会让校准变成
循环论证（误差恒为 0）。
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db import SessionLocal  # noqa: E402
from backend.models import DatasetItem  # noqa: E402

METRICS = [
    "faithfulness",
    "context_precision",
    "context_recall",
    "answer_relevance",
    "answer_correctness",
]


def _score(raw: str, row: int, metric: str) -> float | None:
    text = (raw or "").strip()
    if text == "":
        return None
    try:
        value = float(text)
    except ValueError:
        raise SystemExit(f"第 {row} 行 {metric} 不是数字：{raw!r}")
    if not 0.0 <= value <= 1.0:
        raise SystemExit(f"第 {row} 行 {metric} 超出 [0,1]：{value}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="把人工 gold 分数写回数据库")
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--dataset-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印，不写库")
    args = parser.parse_args()

    with args.csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        raise SystemExit("CSV 没有数据行")
    missing_cols = [c for c in ["item_id", *METRICS] if c not in rows[0]]
    if missing_cols:
        raise SystemExit(f"CSV 缺少列：{missing_cols}")

    s = SessionLocal()
    planned: list[tuple[DatasetItem, dict[str, float]]] = []
    run_ids: set[str] = set()
    try:
        for n, row in enumerate(rows, 2):  # 从 CSV 第 2 行开始
            raw_id = (row.get("item_id") or "").strip()
            if not raw_id.isdigit():
                raise SystemExit(f"第 {n} 行 item_id 非法：{raw_id!r}")
            item_id = int(raw_id)
            item = s.get(DatasetItem, item_id)
            if item is None:
                raise SystemExit(f"第 {n} 行 item_id={item_id} 不存在")
            if item.dataset_id != args.dataset_id:
                raise SystemExit(
                    f"第 {n} 行 item_id={item_id} 属于数据集 #{item.dataset_id}，"
                    f"不是 --dataset-id={args.dataset_id}"
                )

            gold = {}
            for metric in METRICS:
                value = _score(row.get(metric, ""), n, metric)
                if value is not None:
                    gold[metric] = value
            if not gold:
                raise SystemExit(f"第 {n} 行 item_id={item_id} 一个分数都没填")

            if row.get("annotated_on_run"):
                run_ids.add(row["annotated_on_run"].strip())
            planned.append((item, gold))

        print(f"CSV 行数：{len(rows)}，待写入：{len(planned)} 条")
        if run_ids:
            print(f"标注所依据的 run：{', '.join(sorted(run_ids))}")
        for item, gold in planned:
            print(f"  item {item.id}: {json.dumps(gold, ensure_ascii=False)}")

        if args.dry_run:
            print("\n[dry-run] 未写库")
            return

        backup = args.csv_path.with_suffix(
            f".gold-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        backup.write_text(
            json.dumps(
                {
                    "dataset_id": args.dataset_id,
                    "source_csv": str(args.csv_path),
                    "annotated_on_run": sorted(run_ids),
                    "previous": {str(item.id): item.gold_scores for item, _ in planned},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        for item, gold in planned:
            item.gold_scores = json.dumps(gold, ensure_ascii=False)
        s.commit()
        print(f"\n已写入 {len(planned)} 条；旧值备份：{backup}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
