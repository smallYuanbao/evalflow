"""从 `datasets/*.json` 导入评测集。

## 为什么要有这个脚本

`data/eval.db` 在 `.gitignore` 里，换机器、删库之后就没了。评测集必须能从仓库里的
版本文件重建，否则「改了评测集」这件事无法 review，也无法复现历史 run。

导入前会先用 `backend.snapshot.content_hash` 重算 `dataset_hash`，与文件里记录的值
比对——不一致说明文件被手改过或导出不完整，直接拒绝导入，避免把错误数据带进库里。

## 用法

    .venv/bin/python scripts/import_dataset.py datasets/babyai-e2e-v3.json

同名评测集已存在时默认拒绝（防止重复导入）；确需再导入一份用 `--allow-duplicate`。

## 不导入什么

- `items[].db_id` / `index`：只用于和旧 run 对照，数据库会分配新 id。
- `dataset_hash`：不入库，run 创建时会按当前条目重新计算并写进快照。
"""

import argparse
import json
import sys
from pathlib import Path

# 直接运行 `python scripts/...` 时 sys.path[0] 是 scripts/，需要把仓库根加进来
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db import SessionLocal, init_db  # noqa: E402
from backend.models import Dataset, DatasetItem  # noqa: E402
from backend.snapshot import content_hash  # noqa: E402


def _load(path: Path) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise SystemExit(f"没有可导入的条目：{path}")

    for i, it in enumerate(items, 1):
        for key in ("input", "expected_output", "bucket"):
            if key not in it:
                raise SystemExit(f"第 {i} 条缺少字段 {key}")

    payload = [
        {"input": it["input"], "expected_output": it["expected_output"], "bucket": it["bucket"]}
        for it in items
    ]
    digest = content_hash(payload)
    recorded = data.get("dataset_hash")
    if recorded and recorded != digest:
        raise SystemExit(
            f"哈希不一致，拒绝导入：\n  文件记录 {recorded}\n  重新计算 {digest}\n"
            "请确认文件是否被手改；若是有意修改，先更新 dataset_hash 再导入。"
        )
    return data, digest


def main() -> None:
    parser = argparse.ArgumentParser(description="从 JSON 版本文件导入评测集")
    parser.add_argument("path", type=Path, help="datasets/*.json")
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="允许创建同名评测集（默认拒绝，防止重复导入）",
    )
    args = parser.parse_args()

    data, digest = _load(args.path)
    init_db()
    s = SessionLocal()
    try:
        if not args.allow_duplicate:
            exists = s.query(Dataset).filter(Dataset.name == data["name"]).first()
            if exists:
                raise SystemExit(
                    f"已存在同名评测集 #{exists.id}「{exists.name}」；"
                    "如确需再导入一份，加 --allow-duplicate"
                )

        ds = Dataset(name=data["name"], description=data.get("description"))
        s.add(ds)
        s.flush()

        for it in data["items"]:
            gold = it.get("gold_scores")
            s.add(
                DatasetItem(
                    dataset_id=ds.id,
                    input=it["input"],
                    expected_output=it["expected_output"],
                    bucket=it["bucket"],
                    gold_scores=json.dumps(gold, ensure_ascii=False) if gold is not None else None,
                )
            )
        s.commit()
        print(f"已导入 #{ds.id}「{ds.name}」{len(data['items'])} 条  dataset_hash={digest}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
