"""gov.cn 政策文件库客户端：按标题检索部委发文，拿附件 PDF。

留在这里有两个用途：一是可达性实测用它跑过第一轮，报告还留着做对照；二是政策
文件库的检索接口比站点搜索规整（有发文机关、发文字号、结构化 JSON），找特定部委
的文件时更快。切分与 PDF 抽取在 tools.fetch 里，两个源共用同一套口径。
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass

from tools import fetch
from tools.fetch import Clause, html_body, pdf_links, pdf_text, split_clauses

__all__ = [
    "Clause",
    "Notice",
    "attachment_pdfs",
    "page_body",
    "pdf_text",
    "search_notices",
    "split_clauses",
]

SEARCH = "https://sousuo.www.gov.cn/search-gov/data"

# 政策文件库的四个分类，部门文件才是部委发文，另三个用来兜住公报刊登的旧文件
CATEGORIES = ("bumenfile", "gongwen", "otherfile", "gongbao")


@dataclass(frozen=True)
class Notice:
    """政策文件库的一条检索命中。"""

    title: str
    url: str
    org: str
    pcode: str
    pubtime: str


def search_notices(keyword: str, *, field: str = "title", size: int = 100) -> list[Notice]:
    """按指定字段检索。field=quanwen 时是全文检索，噪声大得多。"""
    query = urllib.parse.urlencode(
        {"t": "zhengcelibrary", "q": keyword, "searchfield": field, "p": 1, "n": size}
    )
    payload = json.loads(fetch.fetch(f"{SEARCH}?{query}", sleep=0.4))
    # 检索词无命中时 searchVO 为 null，catMap 也可能整个缺席
    cat_map = (payload.get("searchVO") or {}).get("catMap") or {}
    notices: list[Notice] = []
    for name in CATEGORIES:
        for item in cat_map.get(name, {}).get("listVO") or []:
            notices.append(
                Notice(
                    title=fetch.plain(item.get("title", "")),
                    url=item.get("url", ""),
                    org=item.get("puborg", "") or "",
                    pcode=item.get("pcode", "") or "",
                    pubtime=item.get("pubtimeStr", "") or "",
                )
            )
    return notices


def attachment_pdfs(page_url: str) -> list[str]:
    return pdf_links(fetch.fetch(page_url).decode("utf-8", "ignore"), page_url)


def page_body(page_url: str) -> str:
    return html_body(fetch.fetch(page_url).decode("utf-8", "ignore"))
