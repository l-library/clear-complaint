"""导出可以直接上传到平台知识库的文件集。

平台上「知识检索」节点的输出带文件名，引用最终会显示给用户，所以文件名必须是人
读得懂的。原始下载名 `1645425789350_85133.pdf` 直接入库，用户看到的就是
「依据：1645425789350_85133」——这一步做的就是把它变成
「儿童及青少年鼻咽癌诊疗规范.txt」。

同时产出 kb_manifest.csv：文件名、标题、域标签、来源、sha256、字数。平台侧要按它
打文档标签（单库只能挂一个，九个域只能靠标签分区）。

用法：uv run python -m tools.build_kb
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from tools import domains, roles

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
TEXT = CORPUS / "text"
KB = CORPUS / "kb"

# 平台文件名里不能出现这些字符，路径分隔符尤其不能留
_ILLEGAL = re.compile(r'[\\/:*?"<>|\n\r\t]+')
# 部委发文标题里的套话，进入库名之前全部剥掉
_PREFIXES = (
    "国家卫生健康委办公厅关于印发",
    "国家卫生健康委办公厅关于",
    "国家卫生健康委关于印发",
    "国家卫生健康委关于",
    "关于印发",
    "关于",
    "卫生部关于印发",
)
_SUFFIXES = ("的通知", "的通告", "的函")
_ATTACHMENT = re.compile(r"^附件\s*[\d一二三四五六七八九十]+[-—]?\d*\s*")

MANIFESTS = ("manifest.json", "manifest_govcn.json")


@dataclass
class Document:
    slug: str
    title: str
    filename: str
    origin: str
    sha256: str
    chars: int
    tags: list[str]


def filename_for(title: str, slug: str) -> str:
    """把发文标题折成一个能读、能进平台的文件名（不含扩展名）。"""
    name = _ATTACHMENT.sub("", title).strip()
    changed = True
    while changed:
        changed = False
        for prefix in _PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix) :].strip()
                changed = True
    for suffix in _SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    name = _ILLEGAL.sub("-", name).strip(" -.")
    # 剥完还是空，或者压根没有中文可读信息，就退回一个可读的兜底名
    if len(name) < 4 or not re.search(r"[\u4e00-\u9fff]", name):
        name = slug
    return name[:60]


# 词表按病名组织，覆盖不到「域」本身的名字，补一小张标题提示表
TITLE_HINTS: tuple[tuple[str, str], ...] = (
    ("动物致伤", "伤口与动物致伤"),
    ("咬伤", "伤口与动物致伤"),
    ("分级诊疗", "慢病随访"),
    ("健康服务规范", "慢病随访"),
)


def _vocab_domains() -> list[tuple[str, str]]:
    """（词面，域）对，词面含病名与口语别名，按长度降序以便最长匹配。"""
    payload = json.loads((CORPUS / "vocab.json").read_text(encoding="utf-8"))
    pairs = [
        (surface, row["domain"])
        for row in payload["terms"]
        for surface in (row["name"], *row["aliases"])
    ]
    return sorted(pairs, key=lambda pair: -len(pair[0]))


def tags_for(title: str, chunk_tags: set[str]) -> list[str]:
    """标签先看标题里的病名，再看片段的词共现。

    只看词共现会出错：「流行性感冒诊疗方案」的高危人群一节提到高血压与糖尿病，
    就被标成慢病随访；而「手足口病诊疗指南」因为全是儿科描述，反而一个标签都没有。
    标题里的病名是这份文件到底在讲什么的直接证据。
    """
    by_title = {domain for surface, domain in _vocab_domains() if surface and surface in title}
    by_title.update(domain for hint, domain in TITLE_HINTS if hint in title)
    if by_title:
        return sorted(by_title)
    if chunk_tags:
        return sorted(chunk_tags)
    return ["未标注"]


def _documents() -> list[Document]:
    entries: list[dict[str, str | int]] = []
    for name in MANIFESTS:
        path = CORPUS / name
        if path.exists():
            entries.extend(json.loads(path.read_text(encoding="utf-8")))

    chunk_tags: dict[str, set[str]] = {}
    for line in (CORPUS / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["role"] not in ("clinical", "triage"):
            continue
        found = domains.hits(row["text"])
        if found:
            chunk_tags.setdefault(str(row["source"]), set()).update(found)

    documents: list[Document] = []
    used: set[str] = set()
    for entry in entries:
        slug = str(entry["slug"])
        title = str(entry["title"])
        status = str(entry["status"])
        if status not in {"ok", "ocr"}:
            continue
        _, keep, _ = roles.classify(title, slug)
        if not keep or not (TEXT / f"{slug}.txt").exists():
            continue

        base = filename_for(title, slug)
        filename = base
        counter = 2
        while filename in used:
            filename = f"{base}-{counter}"
            counter += 1
        used.add(filename)

        source = str(entry["source"])
        origin = source if source.startswith("http") else f"nhc.gov.cn 手工下载：{source}"
        documents.append(
            Document(
                slug=slug,
                title=title,
                filename=filename,
                origin=origin,
                sha256=str(entry["sha256"])[:16],
                chars=int(entry["chars"]),
                tags=tags_for(title, chunk_tags.get(slug, set())),
            )
        )
    return sorted(documents, key=lambda doc: doc.filename)


def main() -> int:
    if KB.exists():
        shutil.rmtree(KB)
    KB.mkdir(parents=True)

    documents = _documents()
    for doc in documents:
        shutil.copyfile(TEXT / f"{doc.slug}.txt", KB / f"{doc.filename}.txt")

    with (KB / "kb_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["文件名", "标题", "域标签", "来源", "sha256前16位", "字数"])
        for doc in documents:
            writer.writerow(
                [
                    f"{doc.filename}.txt",
                    doc.title,
                    ";".join(doc.tags),
                    doc.origin,
                    doc.sha256,
                    doc.chars,
                ]
            )

    tagged: dict[str, int] = dict.fromkeys(domains.DOMAINS, 0)
    for doc in documents:
        for tag in doc.tags:
            tagged[tag] = tagged.get(tag, 0) + 1
    print(f"[info] 导出 {len(documents)} 份文档到 {KB}")
    print(f"[info] 无域标签 {sum(1 for doc in documents if doc.tags == ['未标注'])} 份")
    for name, count in tagged.items():
        print(f"       {name:12} {count:3} 份")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
