"""把受控表 triage_pool.json 里的片段标记为 triage 角色，使其进入检索池。

为什么不是改 chunk.py 的标题关键词：这批判据住在治疗/预防/流行病学章节里，
按标题分类永远进不了池；而按内容关键词放行会把大批含剂量方剂的治疗段落一起
扫进来，违背「治疗段落不进池」的初衷。受控表是逐条人工策展的，与
red_flags.json、vocab.json 同一性质：可审计、可复现、改表必须过评审。

重建语料的顺序：chunk → triage_pool apply → embed。

用法：
    uv run python -m tools.triage_pool apply    # 对现有 chunks.jsonl 应用
    uv run python -m tools.triage_pool check    # 校验角色与受控表一致
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
TRIAGE_ROLES = ("clinical", "triage")


def load_table() -> list[dict[str, str]]:
    payload = json.loads((CORPUS / "triage_pool.json").read_text(encoding="utf-8"))
    return [dict(item) for item in payload["chunks"]]


def apply(chunks: list[dict[str, object]]) -> tuple[int, list[str]]:
    """对片段列表应用 triage 角色，返回（改写数、表中不存在的 id）。

    chunk.py 的构建流程也调用这里，保证语料重建后补充池不丢。
    """
    wanted = {item["chunk_id"] for item in load_table()}
    flipped = 0
    missing: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_id = str(chunk["chunk_id"])
        if chunk_id in wanted:
            seen.add(chunk_id)
            if chunk.get("role") != "triage":
                chunk["role"] = "triage"
                flipped += 1
    missing = sorted(wanted - seen)
    return flipped, missing


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    command = args[0] if args else "check"

    rows = [
        json.loads(line)
        for line in (CORPUS / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if command == "apply":
        flipped, missing = apply(rows)
        if missing:
            print(f"[fail] 受控表里有 {len(missing)} 条在 chunks.jsonl 中不存在: {missing}")
            return 1
        with (CORPUS / "chunks.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[ok] 改写 {flipped} 条为 triage 角色，写入 chunks.jsonl")
        return 0

    if command == "check":
        table = {item["chunk_id"] for item in load_table()}
        current = {str(row["chunk_id"]) for row in rows if row.get("role") == "triage"}
        problems = sorted(table ^ current)
        if problems:
            print(f"[fail] 角色与受控表不一致: {problems}")
            return 1
        print(f"[ok] triage 角色 {len(current)} 条，与受控表一致")
        return 0

    print("用法: uv run python -m tools.triage_pool [apply|check]")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
