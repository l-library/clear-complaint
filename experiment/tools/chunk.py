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

from tools import fetch, roles, triage_pool

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
TEXT = CORPUS / "text"

MIN_CHARS, MAX_CHARS = 150, 400

# 这些内容不是正文：目录行、附件编号、页码、纯标题
_NOISE = re.compile(r"^(附件\s*\d+|目\s*录|第?\s*\d+\s*页)$")
_SENTENCE_END = re.compile(r"(?<=[。！？；])")


# 片段的角色决定它能不能进检索池。
# clinical：临床表现、诊断、重症标准、就医与转诊指征——分诊结论与红旗只能引这些。
# treatment：治疗与用药段落。排除有两个理由：一是里面全是剂量与方剂，检索到就会
#            诱发模型输出用药建议；二是它对「该不该就诊、挂什么科」没有信息量。
# background：病原学、流行病学、发病机制等，撑不起一句面向患者的结论。
CLINICAL = (
    "临床表现",
    "诊断",
    "鉴别诊断",
    "实验室检查",
    "分型",
    "重型",
    "重症",
    "危重",
    "就医",
    "就诊",
    "转诊",
    "并发症",
    "预后",
    "筛查",
    "评估",
)
TREATMENT = ("治疗", "救治", "处置", "用药", "中医", "针灸", "护理", "康复")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    title: str
    heading: str
    role: str
    text: str


def _role(heading: str) -> str:
    if any(word in heading for word in TREATMENT):
        return "treatment"
    if any(word in heading for word in CLINICAL):
        return "clinical"
    return "background"


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


def _fallback_chunks(title: str, slug: str, text: str, start: int) -> list[Chunk]:
    """没有条款编号的文件按句切。

    OCR 出来的文本与「正文直接排在网页里」的通知都没有「一、」「（一）」这类编号，
    按编号切会整份丢成零片段——语料里少一份文件，覆盖率就少一截。
    """
    pieces: list[Chunk] = []
    buffer = ""
    for sentence in _SENTENCE_END.split(_clean(text)):
        if not sentence:
            continue
        if len(buffer) + len(sentence) > MAX_CHARS:
            body = _clean(buffer)
            if len(body) >= MIN_CHARS:
                pieces.append(
                    Chunk(
                        chunk_id=f"{slug}#fb{start + len(pieces):03d}",
                        source=slug,
                        title=title,
                        heading="",
                        role="clinical",
                        text=body,
                    )
                )
            buffer = ""
        buffer += sentence
    body = _clean(buffer)
    if len(body) >= MIN_CHARS:
        pieces.append(
            Chunk(
                chunk_id=f"{slug}#fb{start + len(pieces):03d}",
                source=slug,
                title=title,
                heading="",
                role="clinical",
                text=body,
            )
        )
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
                    role=_role(pending_heading),
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
    if not chunks:
        return _fallback_chunks(title, slug, text, 0)
    return chunks


def _kept_sources() -> dict[str, str]:
    """入语料的文件：manual 与 gov.cn 两批 manifest 里角色合格的。"""
    kept: dict[str, str] = {}
    for name in ("manifest.json", "manifest_govcn.json"):
        path = CORPUS / name
        if not path.exists():
            continue
        for entry in json.loads(path.read_text(encoding="utf-8")):
            # ocr 也是可用的正文：扫描件补了文字层就该进语料，否则白 OCR 一遍
            if entry["status"] not in {"ok", "ocr"}:
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

    # 同一段临床描述会在多个版本的文件里重复（新冠就有八版），检索池里留着只会挤占名额
    seen: set[str] = set()
    unique: list[Chunk] = []
    for chunk in chunks:
        key = re.sub(r"\s+", "", chunk.text)[:200]
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    chunks = unique

    payload = [asdict(chunk) for chunk in chunks]
    # 受控表里的分诊判据片段改标为 triage，语料重建后补充池不丢（corpus/triage_pool.json）
    flipped, missing = triage_pool.apply(payload)
    if missing:
        print(f"[warn] triage 受控表有 {len(missing)} 条未命中: {missing}")
    else:
        print(f"[info] triage 判据片段 {flipped} 条标记完成")

    with (CORPUS / "chunks.jsonl").open("w", encoding="utf-8") as handle:
        for row in payload:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    lengths = [len(chunk.text) for chunk in chunks]
    print(f"[info] 文件 {len(sources)} 份，片段 {len(chunks)} 条")
    if lengths:
        median = sorted(lengths)[len(lengths) // 2]
        print(f"[info] 片长 {min(lengths)}–{max(lengths)} 字，中位 {median}")
    covered = {chunk.source for chunk in chunks}
    clinical = [chunk for chunk in chunks if chunk.role == "clinical"]
    print(f"[info] 有片段的文件 {len(covered)} 份，其中 clinical 片段 {len(clinical)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
