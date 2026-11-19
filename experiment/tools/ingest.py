"""把 corpus/raw 里的原始文件抽成纯文本，落 corpus/text/，并产出清单。

支持 PDF（pdftotext）、Word 97 与 docx（libreoffice 转 txt）、整页另存下来的 HTML。
扫描件（图片型 PDF）抽不出字，标出来交给 OCR 或人工，不静默当成空文件。

用法：uv run python -m tools.ingest
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RAW = HERE / "corpus" / "raw"
TEXT = HERE / "corpus" / "text"

# 抽不出正文的判据：图片型 PDF 只会有页眉页脚跑出来
SCANNED_THRESHOLD = 200


@dataclass
class Extracted:
    source: str
    slug: str
    title: str
    sha256: str
    chars: int
    status: str


def slugify(name: str) -> str:
    stem = Path(name).stem
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", stem).strip("-")
    return slug[:80] or "untitled"


def _pdf_text(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"],
        capture_output=True,
        check=False,
        timeout=300,
    )
    return result.stdout.decode("utf-8", "ignore")


def _html_text(path: Path) -> str:
    markup = path.read_text(encoding="utf-8", errors="ignore")
    markup = re.sub(r"<script.*?</script>|<style.*?</style>", "", markup, flags=re.S)
    text = re.sub(r"<(br|/p|/div|/tr|/h\d)[^>]*>", "\n", markup)
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"<[^>]+>", " ", text))


def _office_texts(paths: list[Path]) -> dict[str, str]:
    """libreoffice 一次转一批，逐条起进程太慢。"""
    if not paths:
        return {}
    out = Path(tempfile.mkdtemp(prefix="ingest-"))
    try:
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "txt:Text",
                "--outdir",
                str(out),
                *[str(p) for p in paths],
            ],
            check=False,
            capture_output=True,
            timeout=900,
        )
        texts: dict[str, str] = {}
        for path in paths:
            produced = out / f"{path.stem}.txt"
            if produced.exists():
                texts[path.name] = produced.read_text(encoding="utf-8", errors="ignore")
        return texts
    finally:
        shutil.rmtree(out, ignore_errors=True)


# 这些文件的第一行常常是「附件 1」之类的编号，标题在它后面几行
_TITLE_HINT = re.compile(r"(诊疗|指南|规范|方案|指标|标准|流程图)")
_TITLE_HINT_LINES = 12


def _normalize(text: str) -> str:
    """去掉行尾空白与全文首尾空行。

    pdftotext 的 -layout 会留下大量行尾空格，既过不了仓库的空白检查，也让切出来的
    条款带着一串无用空格。只动行尾，不动行内内容，逐字核验靠的就是行内文本。
    """
    lines = [line.replace("\t", "    ").rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip() + "\n"


def _title(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = re.sub(r"\s+", " ", line.strip().lstrip("\ufeff"))
        if len(stripped) >= 4:
            lines.append(stripped)
        if len(lines) >= _TITLE_HINT_LINES:
            break
    for line in lines:
        if _TITLE_HINT.search(line) and len(line) >= 8:
            return line[:80]
    return lines[0][:80] if lines else ""


def main() -> int:
    sources = sorted(p for p in RAW.iterdir() if p.is_file())
    office = [p for p in sources if p.suffix.lower() in {".doc", ".docx"} and p.stat().st_size]
    office_text = _office_texts(office)

    TEXT.mkdir(parents=True, exist_ok=True)
    results: list[Extracted] = []
    for path in sources:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = _pdf_text(path)
        elif suffix in {".doc", ".docx"}:
            text = office_text.get(path.name, "")
        elif suffix in {".html", ".htm"}:
            text = _html_text(path)
        else:
            continue

        body = _normalize(text).lstrip("\ufeff")
        if not body:
            status = "empty"
        elif len(body) < SCANNED_THRESHOLD and suffix == ".pdf":
            status = "scanned"
        else:
            status = "ok"

        slug = slugify(path.name)
        if status == "ok":
            (TEXT / f"{slug}.txt").write_text(body, encoding="utf-8")
        results.append(
            Extracted(
                source=path.name,
                slug=slug,
                title=_title(body),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                chars=len(body),
                status=status,
            )
        )

    # 原始 PDF 体积大且含扫描件，不提交；sha256 与 title 让它仍可被核对
    (HERE / "corpus" / "manifest.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = [r for r in results if r.status == "ok"]
    print(f"[info] 文件 {len(results)} 个，可抽正文 {len(ok)} 个，共 {sum(r.chars for r in ok)} 字")
    for r in results:
        if r.status != "ok":
            print(f"[warn] {r.status:8} {r.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
