"""gov.cn 政策文件库的最小客户端：检索通知、取附件、抽正文、切条款。

只用标准库，PDF 转文本交给系统的 pdftotext，避免为一次语料抓取引入依赖。
所有响应按 URL 哈希缓存在 .cache/ 下，重跑不再打网络。
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

CACHE = Path(__file__).resolve().parent.parent / ".cache"
SEARCH = "https://sousuo.www.gov.cn/search-gov/data"

# 政策文件库里的四个分类，部门文件才是部委发文，另外三个分类用来兜住公报刊登的旧文件
CATEGORIES = ("bumenfile", "gongwen", "otherfile", "gongbao")

# 一级条款「一、临床表现」，二级条款「（一）传染源。」
_CLAUSE_L1 = re.compile(r"^\s*[一二三四五六七八九十]{1,3}、")
_CLAUSE_L2 = re.compile(r"^\s*[（(][一二三四五六七八九十]{1,3}[）)]")
_CLAUSE_L3 = re.compile(r"^\s*\d+[.．、]\s*\S")

# gov.cn 的正文页把噪声塞在尾部这几个区块里，切条款前先截掉
_TAIL_MARKERS = ("链接：", "扫一扫在手机打开当前页", "版权所有：中国政府网")


@dataclass(frozen=True)
class Notice:
    """政策文件库的一条检索命中。"""

    title: str
    url: str
    org: str
    pcode: str
    pubtime: str


@dataclass(frozen=True)
class Clause:
    """指南里的一个条款，heading 是它所在的一二级标题路径。"""

    heading: str
    text: str


def _cache_path(url: str, suffix: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}{suffix}"


def fetch(url: str, *, sleep: float = 0.4) -> bytes:
    """带缓存的 GET。缓存命中不打网络，抓取可重复且不重复消耗对方带宽。"""
    cached = _cache_path(url, ".bin")
    if cached.exists():
        return cached.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.gov.cn/"})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                body: bytes = resp.read()
            cached.write_bytes(body)
            time.sleep(sleep)
            return body
        except Exception as exc:  # noqa: BLE001 - 网络层错误统一重试
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"抓取失败: {url}") from last


def _plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def search_notices(keyword: str, *, field: str = "title", size: int = 100) -> list[Notice]:
    """按标题字段检索政策文件库。field=quanwen 时是全文检索，噪声大得多。"""
    query = urllib.parse.urlencode(
        {"t": "zhengcelibrary", "q": keyword, "searchfield": field, "p": 1, "n": size}
    )
    payload = json.loads(fetch(f"{SEARCH}?{query}", sleep=0.4))
    # 检索词无命中时 searchVO.searchId 为 null，catMap 也可能整个缺席
    cat_map = (payload.get("searchVO") or {}).get("catMap") or {}
    notices: list[Notice] = []
    for name in CATEGORIES:
        for item in cat_map.get(name, {}).get("listVO") or []:
            notices.append(
                Notice(
                    title=_plain(item.get("title", "")),
                    url=item.get("url", ""),
                    org=item.get("puborg", "") or "",
                    pcode=item.get("pcode", "") or "",
                    pubtime=item.get("pubtimeStr", "") or "",
                )
            )
    return notices


def attachment_pdfs(page_url: str) -> list[str]:
    """正文页上的本站 PDF 附件。附件都在 gov.cn 自己名下，不跳去 nhc.gov.cn。"""
    page = fetch(page_url).decode("utf-8", "ignore")
    hrefs = re.findall(r'href="([^"]+\.pdf)"', page, flags=re.IGNORECASE)
    urls = {urllib.parse.urljoin(page_url, href) for href in hrefs}
    return sorted(url for url in urls if urllib.parse.urlparse(url).netloc.endswith("gov.cn"))


def pdf_text(pdf_url: str) -> str:
    """PDF 转文本，走系统 pdftotext，版面保留以便按行切条款。"""
    pdf = _cache_path(pdf_url, ".pdf")
    if not pdf.exists():
        pdf.write_bytes(fetch(pdf_url))
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {pdf_url}: {result.stderr[:200]!r}")
    return result.stdout.decode("utf-8", "ignore")


def page_body(page_url: str) -> str:
    """没有附件时的兜底：把正文页的 HTML 直接转成纯文本。"""
    page = fetch(page_url).decode("utf-8", "ignore")
    page = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = _plain(re.sub(r"<(br|/p|/div|/tr)[^>]*>", "\n", page))
    return re.sub(r"\n{3,}", "\n\n", text)


def _trim_tail(text: str) -> str:
    for marker in _TAIL_MARKERS:
        index = text.find(marker)
        if index > 0:
            text = text[:index]
    return text


def split_clauses(text: str) -> list[Clause]:
    """按指南原有的条款编号切分，保留一二级标题路径。

    指南的骨架是「一、病原学」「（一）传染源」这类编号，按它切出来的条款
    天然自带章节归属，后续筛「临床表现 / 诊断 / 就医指征」不必再做语义判断。
    """
    body = _trim_tail(text)
    clauses: list[Clause] = []
    l1 = ""
    l2 = ""
    buffer: list[str] = []

    def flush() -> None:
        joined = " ".join(line.strip() for line in buffer if line.strip())
        joined = re.sub(r"\s{2,}", " ", joined).strip()
        if joined:
            heading = " / ".join(part for part in (l1, l2) if part)
            clauses.append(Clause(heading=heading, text=joined))

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _CLAUSE_L1.match(line):
            flush()
            buffer.clear()
            l1 = line
            l2 = ""
            continue
        if _CLAUSE_L2.match(line):
            flush()
            buffer.clear()
            l2 = line
            continue
        buffer.append(line)
    flush()
    return clauses


def has_attachment(page_url: str) -> bool:
    return bool(attachment_pdfs(page_url))


__all__ = [
    "Clause",
    "Notice",
    "attachment_pdfs",
    "fetch",
    "has_attachment",
    "page_body",
    "pdf_text",
    "search_notices",
    "split_clauses",
]


# 从二级条款里再拆出三级，供后续更细的分片使用；当前探针不需要
if __name__ == "__main__":  # pragma: no cover
    print(_CLAUSE_L3.pattern)
