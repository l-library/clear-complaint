"""从金标准未填的病例文件生成盲标注底稿。

标注者只看画像与主诉，看不到金标准、intent 与引文——这些在
cases/families_proposal.jsonl 里，只供裁决阶段对照。
顺序固定打乱（种子写死，可复现），同族病例不相邻，避免标注者顺手沿用
上一条同主诉的答案。金标准已回填的文件拒绝生成：签收后的病例再出
底稿会把答案带出去。

用法：
    uv run python -m tools.annotation_sheet cases/families.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SEED = 20261202


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("cases/families.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("cases/families_annotation_sheet.jsonl"))
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(row.get("gold") is not None for row in rows):
        print("[error] 金标准已填，拒绝生成盲底稿：签收后的文件不能再出标注材料")
        return 1

    sheet = [
        {
            "case_id": row["case_id"],
            "domain": row["domain"],
            "portrait": row["portrait"],
            "V1": row["variants"]["V1"],
        }
        for row in rows
    ]
    rng = random.Random(SEED)
    for _ in range(200):
        rng.shuffle(sheet)
        if all(
            sheet[i]["case_id"][:3] != sheet[i + 1]["case_id"][:3] for i in range(len(sheet) - 1)
        ):
            break
    args.out.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in sheet),
        encoding="utf-8",
    )
    print(f"[ok] {args.out}，{len(sheet)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
