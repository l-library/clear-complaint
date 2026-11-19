"""把 corpus/text 切成引用片段，落 corpus/chunks.jsonl。

片长 150–400 字：低于 150 的片段撑不起一条「可能相关情况」的依据，高于 400 的
片段在 topk=5 的检索池里挤占名额。切分仍按文件自己的条款编号，条款本身超长时
在句末切，条款过短时与同章节的下一条合并，所以一个片段永远只属于一个章节。

用法：uv run python -m tools.chunk
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from tools import fetch, roles

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
TEXT = CORPUS / "text"

MIN_CHARS, MAX_CHARS = 150, 400

# 这些内容不是正文：目录行、附件编号、页码、纯标题
_NOISE = re.compile(r"^(附件\s*\d+|目\s*录|第?\s*\d+\s*页)$")
_SENTENCE_END = re.compile(r"(?<=[。！？；])")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    title: str
    heading: str
    text: str


def _clean(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def _split_long(text: str) -> list[str]:
    """超长条款在句末切开，仍超长的按上限硬切，避免一个片段吃掉整个章节。"""
    pieces: list[str] = []
    buffer = ""
    for sentence in _SENTENCE_END.split(text):
        if not sentence:
            continue
        if len(buffer) + len(sentence) <= MAX_CHARS:
            buffer += sentence
            continue
        if buffer:
            pieces.append(buffer)
        buffer = sentence
        while len(buffer) > MAX_CHARS:
            pieces.append(buffer[:MAX_CHARS])
            buffer = buffer[MAX_CHARS:]
    if buffer:
        pieces.append(buffer)
    return pieces


def _chunks_for(title: str, slug: str, text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending = ""
    pending_heading = ""

    def flush() -> None:
        nonlocal pending, pending_heading
        body = _clean(pending)
        if len(body) >= MIN_CHARS:
            chunks.append(
                Chunk(
                    chunk_id=f"{slug}#{len(chunks):03d}",
                    source=slug,
                    title=title,
                    heading=pending_heading,
                    text=body,
                )
            )
        pending = ""

    for clause in fetch.split_clauses(text):
        body = _clean(clause.text)
        if not body or _NOISE.match(body):
            continue
        if not pending:
            pending_heading = clause.heading
        for piece in _split_long(body):
            if len(pending) + len(piece) + 1 > MAX_CHARS:
                flush()
                pending_heading = clause.heading
            pending = f"{pending} {piece}".strip() if pending else piece
            if len(pending) >= MIN_CHARS:
                flush()
    flush()
    return chunks


def _kept_sources() -> dict[str, str]:
    """入语料的文件：manual 与 gov.cn 两批 manifest 里角色合格的。"""
    kept: dict[str, str] = {}
    for name in ("manifest.json", "manifest_govcn.json"):
        path = CORPUS / name
        if not path.exists():
            continue
        for entry in json.loads(path.read_text(encoding="utf-8")):
            if entry["status"] != "ok":
                continue
            _, keep, _ = roles.classify(entry["title"], entry["slug"])
            if keep:
                kept[entry["slug"]] = entry["title"]
    return kept


def main() -> int:
    sources = _kept_sources()
    chunks: list[Chunk] = []
    for slug, title in sorted(sources.items()):
        path = TEXT / f"{slug}.txt"
        if not path.exists():
            continue
        chunks.extend(_chunks_for(title, slug, path.read_text(encoding="utf-8")))

    with (CORPUS / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(asdict(chunk), ensure_ascii=False) + "\n")

    lengths = [len(chunk.text) for chunk in chunks]
    print(f"[info] 文件 {len(sources)} 份，片段 {len(chunks)} 条")
    if lengths:
        median = sorted(lengths)[len(lengths) // 2]
        print(f"[info] 片长 {min(lengths)}–{max(lengths)} 字，中位 {median}")
    covered = {chunk.source for chunk in chunks}
    print(f"[info] 有片段的文件 {len(covered)} 份")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
