"""语料可达性实测：以 nhc.gov.cn 为单一来源，按病种统计可切分片段数。

域的口径是「病种」而不是「症状」：卫健委公开的诊疗方案与指南覆盖的是病种，
症状级指南由中华医学会各分会发布、全文在付费期刊库，既不能入库也不能逐字公开
引用。主诉照样写患者口吻，但每个域背后必须有一份可核、可分发的依据。

用法：uv run python -m tools.probe_nhc
"""

from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from tools import fetch, nhc

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"

# 候选病种域。关键词只用来给片段归类，不做临床判断；归类结果是给人工锁域用的
# 下界估计，最终哪些病种进语料由人看「文件 × 域」表决定。
DOMAINS: dict[str, tuple[str, ...]] = {
    "流行性感冒": ("流感", "流行性感冒", "甲型", "乙型", "抗病毒"),
    "新型冠状病毒感染": ("新型冠状", "新冠", "奥密克戎", "新冠病毒"),
    "麻疹": ("麻疹", "麻疹病毒", "麻疹疫苗", "出疹"),
    "水痘": ("水痘", "带状疱疹", "水疱"),
    "手足口病": ("手足口", "EV71", "柯萨奇", "疱疹性咽峡炎"),
    "病毒性腹泻": ("诺如", "轮状", "腹泻", "水样便", "呕吐"),
    "细菌性痢疾": ("痢疾", "志贺", "脓血便", "里急后重"),
    "猩红热": ("猩红热", "草莓舌", "链球菌"),
    "百日咳": ("百日咳", "痉咳", "鸡鸣样"),
    "肺结核": ("结核", "结核分枝杆菌", "抗结核"),
    "动物致伤": ("狂犬", "犬咬伤", "动物致伤", "破伤风", "暴露后"),
    "发热伴血小板减少": ("血小板减少", "蜱", "布尼亚"),
    "猴痘": ("猴痘", "mpox", "痘疹"),
    "登革热": ("登革", "伊蚊", "蚊媒"),
    "肥胖症": ("肥胖", "体质指数", "体重"),
    "近视": ("近视", "屈光", "视力"),
    "慢性病分级诊疗": ("高血压", "糖尿病", "冠心病", "慢阻肺", "脑卒中", "转诊"),
    "老年健康": ("老年", "衰弱", "跌倒", "失能"),
}

# 可作引用源的章节：临床表现、诊断、重症标准、就医指征、治疗
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
    "预后",
)

MIN_CLAUSE, MAX_CLAUSE = 30, 600
MIN_PER_DOMAIN = 8

# 标题里没有这些词的文件不是诊疗类文件，早期版本就是靠这条把宠物诊疗秩序、
# 山洪灾害防治这类无关文件挡掉的
RELEVANT_TITLE = ("诊疗", "指南", "规范", "方案", "标准")


@dataclass
class DocResult:
    title: str
    url: str
    pdfs: list[str] = field(default_factory=list)
    clauses: int = 0
    error: str = ""


def _domain_hits(text: str) -> set[str]:
    """一个条款命中某病种至少两个关键词才算提及，压掉偶然共现。"""
    hits: set[str] = set()
    for name, words in DOMAINS.items():
        if sum(1 for word in words if word in text) >= 2:
            hits.add(name)
    return hits


def _is_citable(heading: str) -> bool:
    return any(section in heading for section in CITABLE_SECTIONS)


def _page_title(markup: str, fallback: str) -> str:
    match = re.search(r"<title>(.*?)</title>", markup, flags=re.S)
    if not match:
        return fallback
    return re.sub(r"\s+", " ", fetch.plain(match.group(1))).strip()


def _harvest(session: nhc.Session, hit: nhc.Hit) -> DocResult:
    result = DocResult(title=hit.title, url=hit.url)
    try:
        markup = session.article(hit.url)
        if not markup:
            result.error = "正文页未取到"
            return result
        # 搜索结果的标题被截断，正文页的 <title> 才完整，用它做后续的标题过滤
        result.title = _page_title(markup, hit.title)
        result.pdfs = nhc.attachments(markup, hit.url)
        if result.pdfs:
            for pdf in result.pdfs:
                result.clauses += len(fetch.split_clauses(fetch.pdf_text(pdf)))
        else:
            # 少数通知把正文直接排在页面里，没有附件
            result.clauses = len(fetch.split_clauses(fetch.html_body(markup)))
    except Exception as exc:  # noqa: BLE001 - 记录失败，不让单篇中断整轮
        result.error = f"{type(exc).__name__}: {exc}"[:200]
    return result


def main() -> int:
    hits = nhc.candidates()
    print(f"[info] 候选文件 {len(hits)} 条")
    if not hits:
        return 1

    # 一个浏览器会话不能并发，正文页串行取；附件走普通 HTTP，慢在下载而不在渲染
    with nhc.Session() as session:
        results = []
        for index, hit in enumerate(hits, 1):
            print(f"[info] {index}/{len(hits)} {hit.title[:48]}")
            results.append(_harvest(session, hit))

    relevant = [r for r in results if any(k in r.title for k in RELEVANT_TITLE)]
    skipped = len(results) - len(relevant)
    print(f"[info] 诊疗类标题 {len(relevant)} 条，非诊疗类 {skipped} 条不入统计")
    failed = [r for r in results if r.error]
    print(f"[info] 正文页失败 {len(failed)} 条")

    mentions: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    citable: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    docs: dict[str, set[str]] = {name: set() for name in DOMAINS}
    per_doc: dict[str, dict[str, int]] = {}
    total = 0

    for result in results:
        if result.error:
            continue
        for source in result.pdfs or [result.url]:
            try:
                raw = fetch.pdf_text(source) if result.pdfs else ""
            except Exception:  # noqa: BLE001 - 统计阶段忽略单篇失败
                continue
            for clause in fetch.split_clauses(raw):
                if not (MIN_CLAUSE <= len(clause.text) <= MAX_CLAUSE):
                    continue
                total += 1
                for name in _domain_hits(clause.text):
                    mentions[name] += 1
                    if _is_citable(clause.heading):
                        citable[name] += 1
                        docs[name].add(result.title)
                        row = per_doc.setdefault(result.title, dict.fromkeys(DOMAINS, 0))
                        row[name] += 1

    CORPUS.mkdir(parents=True, exist_ok=True)
    (CORPUS / "nhc_sources.json").write_text(
        json.dumps([dataclasses.asdict(r) for r in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = _render(results, mentions, citable, docs, per_doc, total)
    (CORPUS / "probe_nhc.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def _render(
    results: list[DocResult],
    mentions: dict[str, int],
    citable: dict[str, int],
    docs: dict[str, set[str]],
    per_doc: dict[str, dict[str, int]],
    total: int,
) -> str:
    ok = [r for r in results if not r.error and r.clauses]
    failed = [r for r in results if r.error]
    lines = [
        "# 语料可达性实测 · nhc.gov.cn",
        "",
        "由 `tools/probe_nhc.py` 生成。单一来源：国家卫生健康委官网（政务公开主动公开内容）。",
        "",
        f"- 候选文件 {len(results)} 条，取到正文 {len(ok)} 条，失败 {len(failed)} 条",
        f"- 参与统计的条款 {total} 条（{MIN_CLAUSE}–{MAX_CLAUSE} 字）",
        "- 「可用片段」= 命中该病种至少两个关键词，且落在可引章节的条款数",
        "- 判定要求可用片段 ≥ 8 且来自 ≥ 2 份文件",
        "",
        "## 病种 × 片段数",
        "",
        "| 病种 | 提及片段 | 可用片段 | 涉及文件 | 判定 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name in DOMAINS:
        if citable[name] >= MIN_PER_DOMAIN and len(docs[name]) >= 2:
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
        "## 文件 × 病种（可用片段数）",
        "",
        "| 文件 | " + " | ".join(DOMAINS) + " |",
        "| --- | " + " | ".join("---" for _ in DOMAINS) + " |",
    ]
    for title, counts in sorted(per_doc.items(), key=lambda item: -sum(item[1].values())):
        cells = " | ".join(str(counts[name]) if counts[name] else "" for name in DOMAINS)
        lines.append(f"| {title[:34]} | {cells} |")

    lines += [
        "",
        "## 文件清单",
        "",
        "| 标题 | 附件 | 条款 | 状态 |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        status = f"失败：{result.error}" if result.error else "ok"
        title = result.title[:44]
        lines.append(
            f"| [{title}]({result.url}) | {len(result.pdfs)} | {result.clauses} | {status} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
