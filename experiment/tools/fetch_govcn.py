"""从 gov.cn 政策文件库补齐传染病诊疗方案，落 corpus/text/。

政策文件库没有动态防护，附件 PDF 也都是 gov.cn 自己名下的直链，所以这一路可以
脚本化、可复现。它覆盖的正是症状最丰富的一批文件：麻疹、水痘、手足口、菌痢、
猩红热、百日咳、登革热、猴痘、结核等，这些文件的「临床表现 / 重症与危重症标准 /
就医指征」章节是皮疹、腹泻、发热、呼吸道四个域和红旗清单的主要来源。

用法：uv run python -m tools.fetch_govcn
"""

from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from tools import fetch, govcn

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
TEXT = CORPUS / "text"

# 标题检索词。都收敛到「诊疗方案 / 防治指南」这类体例，避免捞到管理办法
KEYWORDS = (
    "传染病诊疗方案",
    "诊疗方案",
    "手足口病",
    "水痘",
    "猩红热",
    "细菌性痢疾",
    "百日咳",
    "登革热",
    "猴痘",
    "肺结核",
    "动物致伤",
    "破伤风",
    # 这两批是「一个通知带十来个病种」的合集，标题里没有单个病种名，
    # 只能按合集的首个病种检索：鼠疫等 11 种（含水痘、菌痢、猩红热、流脑、
    # 炭疽、布鲁氏菌、黑热病、发热伴血小板减少）与麻疹等 3 种
    "鼠疫",
    "炭疽",
    "流行性脑脊髓膜炎",
    "发热伴血小板减少",
)

# 只认卫生系统发文，「诊疗」二字会捞进宠物诊疗秩序、山洪防治这类非临床文件
MEDICAL_ORG = ("卫生健康", "中医药", "疾病预防控制", "疾控")
# 同一病种的多个版本只留最新
_VERSION_NOISE = re.compile(r"[（(][^）)]*[）)]|第[一二三四五六七八九十\d]+版|试行|\s")


@dataclass
class Fetched:
    source: str
    slug: str
    title: str
    sha256: str
    chars: int
    status: str


def _slug(title: str) -> str:
    clean = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title).strip("-")
    return f"govcn-{clean[:70]}"


def _is_medical(notice: govcn.Notice) -> bool:
    return any(mark in notice.org for mark in MEDICAL_ORG)


def _stem(title: str) -> str:
    stem = title
    for prefix in ("国家卫生健康委办公厅关于印发", "国家卫生健康委关于印发", "关于印发"):
        stem = stem.replace(prefix, "")
    return _VERSION_NOISE.sub("", stem.replace("的通知", ""))


def _candidates() -> list[govcn.Notice]:
    best: dict[str, govcn.Notice] = {}
    for keyword in KEYWORDS:
        try:
            notices = govcn.search_notices(keyword)
        except Exception as exc:  # noqa: BLE001 - 单个检索词失败不该拖垮整轮
            print(f"[warn] 检索失败 {keyword}: {exc}")
            continue
        for notice in notices:
            if not notice.url or "zhengceku" not in notice.url or not _is_medical(notice):
                continue
            key = _stem(notice.title)
            current = best.get(key)
            if current is None or notice.pubtime > current.pubtime:
                best[key] = notice
    return list(best.values())


def _harvest(notice: govcn.Notice) -> Fetched:
    slug = _slug(notice.title)
    try:
        pdfs = govcn.attachment_pdfs(notice.url)
        digest = hashlib.sha256()
        if pdfs:
            chunks: list[str] = []
            for pdf in pdfs:
                chunks.append(fetch.pdf_text(pdf))
                digest.update(pdf.encode())
            body = fetch.normalize("\n".join(chunks))
        else:
            # 少数通知把指南正文直接排在页面里，没有附件
            body = fetch.normalize(govcn.page_body(notice.url))
            digest.update(notice.url.encode())
        if len(body) < 200:
            return Fetched(notice.url, slug, notice.title, "", len(body), "no-content")
        (TEXT / f"{slug}.txt").write_text(body, encoding="utf-8")
        return Fetched(notice.url, slug, notice.title, digest.hexdigest(), len(body), "ok")
    except Exception as exc:  # noqa: BLE001 - 记录失败，不让单篇中断整轮
        return Fetched(notice.url, slug, notice.title, "", 0, f"error:{type(exc).__name__}")


def main() -> int:
    TEXT.mkdir(parents=True, exist_ok=True)
    notices = _candidates()
    print(f"[info] 候选 {len(notices)} 条")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_harvest, notices))
    (CORPUS / "manifest_govcn.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ok = [r for r in results if r.status == "ok"]
    print(f"[info] 成功 {len(ok)} 条，共 {sum(r.chars for r in ok)} 字")
    for r in results:
        if r.status != "ok":
            print(f"[warn] {r.status:22} {r.title[:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
