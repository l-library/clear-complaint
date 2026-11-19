"""nhc.gov.cn 客户端：站点搜索发现文件，Playwright 过 WAF 取正文页。

国家卫生健康委的主站对普通 HTTP 客户端返回 412（瑞数动态防护），必须先由真实
浏览器执行挑战脚本拿到 cookie，之后的文章页才返回 200。PDF 附件直链不受这道
防护影响，所以正文页走浏览器、附件走普通 HTTP，各用能用的方式。

为什么是这里而不是期刊库：卫健委的诊疗方案是以部委通知形式发布的行政性质文件，
《著作权法》第五条不适用于这类文件，因此可以被复制、入库、公开分发，也就是
「材料里的数字能被评委复现」这条要求唯一能落地的来源。
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tools import fetch

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page, Playwright

SITE_CODE = "bm24000006"
SEARCH = "https://zs.kaipuyun.cn/s"
BASE = "https://www.nhc.gov.cn"

# 站点搜索每条查询只回十来条且不翻页，所以靠关键词数量铺开而不是靠分页
KEYWORDS = (
    "诊疗方案",
    "诊疗指南",
    "诊疗规范",
    "防治指南",
    "健康服务规范",
    "分级诊疗技术方案",
    "医疗质量控制指标",
)

_ARTICLE = re.compile(r'href="(https?://www\.nhc\.gov\.cn/[^"]+\.shtml)"[^>]*>([^<]{2,120})<')


@dataclass(frozen=True)
class Hit:
    title: str
    url: str


class Session:
    """一次浏览器会话。预热首页拿到 cookie 后，正文页才不再返回 412。"""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def __enter__(self) -> Session:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self._headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = self._browser.new_context(
            user_agent=fetch.UA,
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        context.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        self._page = context.new_page()
        self._page.goto(BASE + "/", wait_until="domcontentloaded", timeout=90_000)
        self._page.wait_for_timeout(3_000)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def article(self, url: str) -> str:
        """取文章页 HTML。返回空串表示没拿到，调用方按缺附件处理。"""
        cached = fetch.cache_path(url, ".html")
        if cached.exists():
            return cached.read_text(encoding="utf-8", errors="ignore")
        assert self._page is not None
        response = self._page.goto(url, wait_until="domcontentloaded", timeout=90_000)
        self._page.wait_for_timeout(1_200)
        if response is None or response.status != 200:
            return ""
        markup = self._page.content()
        cached.write_text(markup, encoding="utf-8")
        return markup


def search(keyword: str) -> list[Hit]:
    """用卫健委的站内搜索（拓尔思 kaipuyun）列出候选文件。"""
    query = urllib.parse.urlencode({"siteCode": SITE_CODE, "searchWord": keyword})
    try:
        body = fetch.fetch(f"{SEARCH}?{query}", referer=BASE + "/")
    except Exception:  # noqa: BLE001 - 搜索接口偶发截断，单条失败不该拖垮整轮
        return []
    markup = body.decode("utf-8", "ignore")
    # 检索结果的标题被拆成相邻的几个 <a>（「关于印发拉沙热」+「诊疗方案（2026年版）」），
    # 所以按出现顺序把指向同一 URL 的相邻锚文本拼起来，才是完整标题
    best: dict[str, str] = {}
    buffer_url = ""
    buffer_text = ""
    for match in _ARTICLE.finditer(markup):
        url = match.group(1)
        text = fetch.plain(match.group(2))
        if url == buffer_url:
            buffer_text += text
        else:
            if buffer_url and len(buffer_text) > len(best.get(buffer_url, "")):
                best[buffer_url] = buffer_text
            buffer_url, buffer_text = url, text
    if buffer_url and len(buffer_text) > len(best.get(buffer_url, "")):
        best[buffer_url] = buffer_text
    return [Hit(title=title, url=url) for url, title in best.items()]


def candidates() -> list[Hit]:
    seen: dict[str, Hit] = {}
    for keyword in KEYWORDS:
        for hit in search(keyword):
            seen.setdefault(hit.url, hit)
    return list(seen.values())


def attachments(markup: str, page_url: str) -> list[str]:
    return fetch.pdf_links(markup, page_url)
