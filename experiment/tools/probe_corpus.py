"""语料可达性实测：扫 gov.cn 政策文件库，按主诉域统计可切分片段数。

产出两样东西：候选通知清单（含来源）与「域 × 片段数」报表。主诉域的数量由
这张表决定——低于每域 8 个片段，检索没有选择压力，引用闸门会变成走过场。

用法：uv run python -m tools.probe_corpus
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from tools import fetch, govcn

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"

# 检索词。标题检索精确，用来捞出「关于印发××诊疗方案的通知」这一类文件。
# 疾控局与中医药局也发诊疗类文件，所以不按发文机关过滤，只在报告里记下来。
KEYWORDS = (
    "诊疗方案",
    "诊疗指南",
    "诊疗规范",
    "防治指南",
    "分级诊疗技术方案",
    "传染病诊疗方案",
    "流行性感冒",
    "手足口病",
    "腹泻",
)

# 主诉域的关键词表。用于粗筛片段归属，不做语义判断：命中多词算提及，
# 命中且落在可引章节里才算可用。口径写在报告里，不和「符合临床诊断」混淆。
DOMAINS: dict[str, tuple[str, ...]] = {
    "上呼吸道": ("流涕", "鼻涕", "鼻塞", "咽痛", "咳嗽", "喷嚏", "上呼吸道", "咽部", "咽峡"),
    "发热": ("发热", "体温", "高热", "低热", "热程"),
    "头痛": ("头痛", "头疼", "颅压"),
    "腹痛": ("腹痛", "腹部", "腹肌紧张", "压痛", "腹胀"),
    "腹泻": ("腹泻", "稀便", "水样便", "排便次数", "里急后重", "呕吐"),
    "皮疹": ("皮疹", "斑丘疹", "疱疹", "出疹", "斑疹", "丘疹", "疹"),
    "胸痛": ("胸痛", "胸闷", "胸骨后", "压榨", "心悸"),
    "腰背关节痛": ("腰痛", "背痛", "关节痛", "腰背", "肌痛", "关节"),
    "头晕乏力": ("头晕", "眩晕", "乏力", "疲倦", "精神萎靡"),
    "失眠疲劳": ("失眠", "入睡", "睡眠", "疲劳", "乏力"),
}

# 可作为引用源的章节。指南的「就医指征」「重症与危重症标准」也在这里，
# 红旗清单就从这些章节里抽。
CITABLE_SECTIONS = (
    "临床表现",
    "诊断",
    "鉴别",
    "重型",
    "重症",
    "危重症",
    "就医",
    "就诊",
    "转诊",
    "治疗",
    "并发症",
)

# 分片长度。太短没有信息，太长在 5 个分片的检索池里挤占名额。
MIN_CLAUSE, MAX_CLAUSE = 30, 600
# 每域达到这个片段数才算覆盖得住，依据见 docs/stage1.md 的「语料」一节
MIN_PER_DOMAIN = 8

# 只认卫生系统发的文件。「诊疗」两个字太泛，会捞进宠物诊疗秩序、山洪防治、
# 地下水污染防治这些非临床文件，它们在整轮统计里能贡献几十条干扰条款。
MEDICAL_ORG = ("卫生健康", "卫生健康委", "中医药", "疾病预防控制", "疾控")

# 同一份指南的多个版本只留最新：新冠一个病就有八个版本，全算进去会把
# 发热域的片段数抬到没有意义的高度
_VERSION_NOISE = re.compile(r"[（(][^）)]*[）)]|第[一二三四五六七八九十\d]+版|试行|\s")


@dataclass
class DocResult:
    title: str
    url: str
    org: str
    pcode: str
    pubtime: str
    pdfs: list[str] = field(default_factory=list)
    clauses: int = 0
    error: str = ""


def _is_medical(notice: govcn.Notice) -> bool:
    return any(mark in notice.org for mark in MEDICAL_ORG)


def _title_stem(title: str) -> str:
    """把「新型冠状病毒肺炎诊疗方案（试行第九版）」归并成同一个键。"""
    stem = title
    for prefix in ("关于印发", "国家卫生健康委办公厅关于印发", "国家卫生健康委关于印发"):
        stem = stem.replace(prefix, "")
    stem = stem.replace("的通知", "").replace("等传染病诊疗方案", "传染病诊疗方案")
    return _VERSION_NOISE.sub("", stem)


def _domain_hits(text: str) -> set[str]:
    """一个条款同时命中某域至少两个关键词才算提及。

    单关键词共现太松：动物致伤规范里「关节」出现一次就能给腰背关节痛记一分，
    十份文件叠起来会造出十个「覆盖得住」的域。要求两个词是为了压掉这种偶然命中。
    """
    hits: set[str] = set()
    for name, words in DOMAINS.items():
        matched = sum(1 for word in words if word in text)
        if matched >= 2:
            hits.add(name)
    return hits


def _is_citable(heading: str) -> bool:
    return any(section in heading for section in CITABLE_SECTIONS)


def discover() -> list[govcn.Notice]:
    seen: dict[str, govcn.Notice] = {}
    for keyword in KEYWORDS:
        try:
            notices = govcn.search_notices(keyword)
        except Exception as exc:  # noqa: BLE001 - 单个检索词失败不该拖垮整轮
            print(f"[warn] 检索失败 {keyword}: {exc}", file=sys.stderr)
            continue
        for notice in notices:
            if not notice.url or "zhengceku" not in notice.url:
                continue
            if not _is_medical(notice):
                continue
            key = _title_stem(notice.title)
            current = seen.get(key)
            if current is None or notice.pubtime > current.pubtime:
                seen[key] = notice
        print(f"[info] {keyword}: +{len(notices)} 条命中，累计 {len(seen)}")
    return list(seen.values())


def harvest(notice: govcn.Notice) -> DocResult:
    result = DocResult(
        title=notice.title,
        url=notice.url,
        org=notice.org,
        pcode=notice.pcode,
        pubtime=notice.pubtime,
    )
    try:
        pdfs = govcn.attachment_pdfs(notice.url)
        result.pdfs = pdfs
        if pdfs:
            for pdf in pdfs:
                result.clauses += len(fetch.split_clauses(fetch.pdf_text(pdf)))
        else:
            # 少数通知把方案正文直接排在 HTML 里，没有附件
            result.clauses = len(fetch.split_clauses(govcn.page_body(notice.url)))
    except Exception as exc:  # noqa: BLE001 - 记录失败，不让单篇文档中断整轮
        result.error = f"{type(exc).__name__}: {exc}"[:200]
    return result


def main() -> int:
    notices = discover()
    print(f"[info] 候选通知 {len(notices)} 条")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(harvest, notices))

    domain_mentions: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    domain_citable: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    domain_docs: dict[str, set[str]] = {name: set() for name in DOMAINS}
    per_doc_domains: dict[str, dict[str, int]] = {}
    total_clauses = 0

    for result in results:
        if result.error:
            continue
        sources = result.pdfs or [result.url]
        for source in sources:
            try:
                raw = fetch.pdf_text(source) if result.pdfs else govcn.page_body(result.url)
            except Exception:  # noqa: BLE001 - 统计阶段忽略单篇失败
                continue
            for clause in fetch.split_clauses(raw):
                if not (MIN_CLAUSE <= len(clause.text) <= MAX_CLAUSE):
                    continue
                total_clauses += 1
                for name in _domain_hits(clause.text):
                    domain_mentions[name] += 1
                    if _is_citable(clause.heading):
                        domain_citable[name] += 1
                        domain_docs[name].add(result.title)
                        row = per_doc_domains.setdefault(result.title, dict.fromkeys(DOMAINS, 0))
                        row[name] += 1

    CORPUS.mkdir(parents=True, exist_ok=True)
    payload = [dataclasses.asdict(result) for result in results]
    (CORPUS / "candidates.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = _render(
        results, domain_mentions, domain_citable, domain_docs, per_doc_domains, total_clauses
    )
    (CORPUS / "probe_report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def _render(
    results: list[DocResult],
    mentions: dict[str, int],
    citable: dict[str, int],
    docs: dict[str, set[str]],
    per_doc_domains: dict[str, dict[str, int]],
    total_clauses: int,
) -> str:
    ok = [result for result in results if not result.error and result.clauses]
    failed = [result for result in results if result.error]
    lines = [
        "# 语料可达性实测",
        "",
        "由 `tools/probe_corpus.py` 生成，重跑即可复现。",
        "",
        f"- 候选通知 {len(results)} 条，成功取到正文 {len(ok)} 条，失败 {len(failed)} 条",
        f"- 参与统计的条款 {total_clauses} 条（{MIN_CLAUSE}–{MAX_CLAUSE} 字）",
        f"- 「可用片段」= 提及该域且落在可引章节（{'、'.join(CITABLE_SECTIONS)}）里的条款数",
        "",
        "## 域 × 片段数",
        "",
        "判定要求同时满足：可用片段 ≥ 8 且来自 ≥ 3 份文件。单一文件撑起一个域不算覆盖，",
        "因为那样检索池里只有同一份材料的片段，引用没有选择压力。",
        "",
        "口径是关键词共现的下界估计，不等于临床适用性：一个条款命中该域至少两个关键词",
        "才算提及。锁域前要人工过一遍「文件 × 域」表，这个数字只用来淘汰明显不成立的域。",
        "",
        "| 主诉域 | 提及片段 | 可用片段 | 涉及文档 | 判定 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in DOMAINS:
        if citable[name] >= MIN_PER_DOMAIN and len(docs[name]) >= 3:
            verdict = "可用"
        elif citable[name]:
            verdict = "偏薄"
        else:
            verdict = "缺失"
        lines.append(
            f"| {name} | {mentions[name]} | {citable[name]} | {len(docs[name])} | {verdict} |"
        )
    lines += [
        "",
        "## 文件 × 域（可用片段数）",
        "",
        "| 标题 | " + " | ".join(DOMAINS) + " |",
        "| --- | " + " | ".join("---" for _ in DOMAINS) + " |",
    ]
    for title, counts in sorted(per_doc_domains.items(), key=lambda item: -sum(item[1].values())):
        cells = " | ".join(str(counts[name]) if counts[name] else "" for name in DOMAINS)
        lines.append(f"| {title[:38]} | {cells} |")

    lines += [
        "",
        "## 文档清单",
        "",
        "| 发布日 | 标题 | 发文机关 | 附件 | 条款 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in sorted(results, key=lambda item: item.pubtime, reverse=True):
        status = f"失败：{result.error}" if result.error else str(result.clauses)
        lines.append(
            f"| {result.pubtime} | [{result.title}]({result.url}) | "
            f"{result.org[:24]} | {len(result.pdfs)} | {status} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
