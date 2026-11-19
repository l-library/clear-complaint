"""按病种统计已入库语料的可用片段数，产出锁定主诉域的依据。

输入是 tools.ingest 抽出的 corpus/text/*.txt 与 corpus/manifest.json。这一步离线，
不碰网络。角色分类（诊疗方案 / 分级诊疗 / 诊疗规范 / 质量控制指标）与是否入库
写在 corpus/sources.json 里，由人复核后生效；脚本先给一版自动分类做初稿。

用法：uv run python -m tools.probe_ingested
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tools import fetch

HERE = Path(__file__).resolve().parent.parent
CORPUS = HERE / "corpus"
TEXT = CORPUS / "text"

# 病种域。这批语料覆盖的是病种而不是症状，域的名字跟着文件走。
DOMAINS: dict[str, tuple[str, ...]] = {
    "发热待查": ("发热", "体温", "高热", "热程", "稽留热"),
    "呼吸道症状": ("咳嗽", "流涕", "咽痛", "鼻塞", "咳痰", "气促", "呼吸困难"),
    "腹泻呕吐": ("腹泻", "呕吐", "水样便", "稀便", "脱水", "补液"),
    "皮疹": ("皮疹", "斑丘疹", "疱疹", "出血点", "结膜充血"),
    "关节痛": ("关节痛", "关节疼痛", "肌痛", "肌肉酸痛", "关节肿胀"),
    "胸痛心悸": ("胸痛", "胸闷", "心悸", "胸骨后", "压榨性", "心绞痛"),
    "头晕与意识改变": ("头晕", "头痛", "意识障碍", "意识改变", "抽搐", "惊厥"),
    "乏力与水肿": ("乏力", "水肿", "贫血", "活动耐量", "气短"),
    "伤口与动物致伤": ("咬伤", "抓伤", "伤口", "暴露后", "狂犬", "破伤风"),
    "慢病随访": ("血压", "血糖", "血脂", "随访", "分级诊疗", "转诊"),
}

# 可作引用源的章节
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
    "上转",
    "下转",
    "治疗",
    "并发症",
    "预后",
)

MIN_CLAUSE, MAX_CLAUSE = 30, 600
MIN_PER_DOMAIN = 12

# 角色判定：质控指标是医院管理指标，不是诊疗内容，一律不入语料
ROLE_RULES: tuple[tuple[str, str], ...] = (
    ("质量控制指标", "质控指标"),
    ("重点任务及服务流程图", "流程图"),
    ("分级诊疗", "分级诊疗"),
    ("诊疗方案", "诊疗方案"),
    ("诊疗规范", "诊疗规范"),
    ("健康服务规范", "健康服务规范"),
)


@dataclass
class Source:
    slug: str
    title: str
    role: str
    keep: bool
    reason: str
    batch: str


def _classify(title: str, slug: str) -> tuple[str, bool, str]:
    for needle, role in ROLE_RULES:
        if needle in title:
            if role in {"质控指标", "流程图"}:
                return role, False, "与诊疗分诊无关"
            return role, True, ""
    if "诊疗规范" in slug:
        return "诊疗规范", True, ""
    return "未分类", False, "需人工确认角色"


def _domain_hits(text: str) -> set[str]:
    return {name for name, words in DOMAINS.items() if sum(1 for w in words if w in text) >= 2}


def _is_citable(heading: str) -> bool:
    return any(section in heading for section in CITABLE_SECTIONS)


def main() -> int:
    sources: list[Source] = []
    for batch, name in (("manual", "manifest.json"), ("govcn", "manifest_govcn.json")):
        path = CORPUS / name
        if not path.exists():
            continue
        for entry in json.loads(path.read_text(encoding="utf-8")):
            if entry["status"] != "ok":
                continue
            role, keep, reason = _classify(entry["title"], entry["slug"])
            sources.append(Source(entry["slug"], entry["title"], role, keep, reason, batch))

    (CORPUS / "sources.json").write_text(
        json.dumps([asdict(s) for s in sources], ensure_ascii=False, indent=2), encoding="utf-8"
    )

    mentions: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    citable: dict[str, int] = dict.fromkeys(DOMAINS, 0)
    docs: dict[str, set[str]] = {name: set() for name in DOMAINS}
    total_clauses = 0
    per_source: dict[str, dict[str, int]] = {}

    for source in sources:
        path = TEXT / f"{source.slug}.txt"
        if not source.keep or not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for clause in fetch.split_clauses(text):
            if not (MIN_CLAUSE <= len(clause.text) <= MAX_CLAUSE):
                continue
            total_clauses += 1
            for name in _domain_hits(clause.text):
                mentions[name] += 1
                if _is_citable(clause.heading):
                    citable[name] += 1
                    docs[name].add(source.slug)
                    row = per_source.setdefault(source.slug, dict.fromkeys(DOMAINS, 0))
                    row[name] += 1

    report = _render(sources, mentions, citable, docs, per_source, total_clauses)
    (CORPUS / "probe_ingested.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


def _render(
    sources: list[Source],
    mentions: dict[str, int],
    citable: dict[str, int],
    docs: dict[str, set[str]],
    per_source: dict[str, dict[str, int]],
    total_clauses: int,
) -> str:
    kept = [s for s in sources if s.keep]
    dropped = [s for s in sources if not s.keep]
    lines = [
        "# 已入库语料的病种覆盖",
        "",
        "由 `tools/probe_ingested.py` 生成。离线运行，只读 `corpus/text/`。",
        "",
        f"- 入库文件 {len(kept)} 份（手工 {len([s for s in kept if s.batch == 'manual'])}，"
        f"gov.cn {len([s for s in kept if s.batch == 'govcn'])}），未入库 {len(dropped)} 份",
        f"- 参与统计的条款 {total_clauses} 条（{MIN_CLAUSE}–{MAX_CLAUSE} 字）",
        f"- 判定要求可用片段 ≥ {MIN_PER_DOMAIN} 且来自 ≥ 2 份文件",
        "",
        "## 病种 × 片段数",
        "",
        "| 域 | 提及片段 | 可用片段 | 涉及文件 | 判定 |",
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
        "## 文件 × 域（可用片段数）",
        "",
        "| 文件 | " + " | ".join(DOMAINS) + " |",
        "| --- | " + " | ".join("---" for _ in DOMAINS) + " |",
    ]
    by_slug = {s.slug: s for s in kept}
    for slug, counts in sorted(per_source.items(), key=lambda item: -sum(item[1].values())):
        cells = " | ".join(str(counts[name]) if counts[name] else "" for name in DOMAINS)
        title = by_slug[slug].title[:30] or slug[:30]
        lines.append(f"| {title} | {cells} |")

    lines += ["", "## 未入库", "", "| 文件 | 角色 | 原因 |", "| --- | --- | --- |"]
    for source in dropped:
        name = source.title[:44] or source.slug[:44]
        lines.append(f"| {name} | {source.role} | {source.reason} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
