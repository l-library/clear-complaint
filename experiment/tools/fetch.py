"""抓取共用层：带缓存的 GET、PDF 转文本、按条款编号切分。

两个来源客户端（gov.cn 政策文件库、nhc.gov.cn）都建在这上面，切分口径只此一处，
避免两个源各切一套导致片段不可比。
"""

from __future__ import annotations

import hashlib
import html
import http.client
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

# 一级条款「一、临床表现」，二级条款「（一）传染源。」
_CLAUSE_L1 = re.compile(r"^\s*[一二三四五六七八九十]{1,3}、")
_CLAUSE_L2 = re.compile(r"^\s*[（(][一二三四五六七八九十]{1,3}[）)]")

# 正文页尾部这几个区块不是文件内容，切条款前先截掉
_TAIL_MARKERS = ("链接：", "扫一扫在手机打开当前页", "版权所有：中国政府网", "责任编辑：")


@dataclass(frozen=True)
class Clause:
    """文件里的一个条款，heading 是它所在的一二级标题路径。"""

    heading: str
    text: str


def cache_path(url: str, suffix: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{digest}{suffix}"


def fetch(url: str, *, sleep: float = 0.4, referer: str = "https://www.gov.cn/") -> bytes:
    """带缓存的 GET。缓存命中不打网络，抓取可重复且不重复消耗对方带宽。"""
    cached = cache_path(url, ".bin")
    if cached.exists():
        return cached.read_bytes()
    headers = {"User-Agent": UA, "Referer": referer}
    last: Exception | None = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                body: bytes = resp.read()
            cached.write_bytes(body)
            time.sleep(sleep)
            return body
        except http.client.IncompleteRead as exc:
            # 站内搜索接口经常发完结果就切断连接，partial 里的内容是可用的
            if exc.partial:
                cached.write_bytes(exc.partial)
                return exc.partial
            last = exc
        except Exception as exc:  # noqa: BLE001 - 网络层错误统一重试
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"抓取失败: {url}") from last


def plain(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def pdf_text(pdf_url: str) -> str:
    """PDF 转文本，走系统 pdftotext，版面保留以便按行切条款。"""
    pdf = cache_path(pdf_url, ".pdf")
    if not pdf.exists():
        pdf.write_bytes(fetch(pdf_url))
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {pdf_url}: {result.stderr[:200]!r}")
    return result.stdout.decode("utf-8", "ignore")


def html_body(markup: str) -> str:
    stripped = re.sub(r"<script.*?</script>|<style.*?</style>", "", markup, flags=re.S)
    text = plain(re.sub(r"<(br|/p|/div|/tr|/h\d)[^>]*>", "\n", stripped))
    return re.sub(r"\n{3,}", "\n\n", text)


def pdf_links(markup: str, page_url: str) -> list[str]:
    """页面上的 PDF 附件直链，只留同域，避免跳到需要登录的第三方库。"""
    hrefs = re.findall(r'href="([^"]+\.pdf)"', markup, flags=re.IGNORECASE)
    urls = {urllib.parse.urljoin(page_url, href) for href in hrefs}
    host = urllib.parse.urlparse(page_url).netloc
    return sorted(url for url in urls if urllib.parse.urlparse(url).netloc == host)


def _trim_tail(text: str) -> str:
    for marker in _TAIL_MARKERS:
        index = text.find(marker)
        if index > 0:
            text = text[:index]
    return text


def split_clauses(text: str) -> list[Clause]:
    """按文件原有的条款编号切分，保留一二级标题路径。

    这批文件的骨架是「一、病原学」「（一）传染源」这类编号，按它切出来的条款
    天然自带章节归属，后面筛「临床表现 / 诊断 / 就医指征」不必再做语义判断。
    """
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

    for raw_line in _trim_tail(text).splitlines():
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
