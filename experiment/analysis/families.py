"""族口径的分析：配对翻转、零孪生对照、边界模糊集拆分。

与 metrics.py 的差别：metrics 比较各变体与基线的一致率，金标准固定；族的金标准
随条件变化，一致率没有意义，这里比较同一主诉在不同背景条件之间的**配对**差异。
解读规则在 cases/README.md 的「时限与主指标的关系」一节预注册，本模块是它的
代码化：

1. 主信号是配对翻转，不是绝对准确率；
2. base 被答错按时限交叉联读，模糊集单独报告；
3. 边界模糊集（base 侧时限模糊，或 hi 侧时限「立即」的档位天花板）与全集分开报；
4. 零孪生 C 是提示词区块噪声的对照，不翻级才是正常。

用法：
    uv run python -m analysis.families runs/<file>.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from analysis.metrics import dedupe, load

TRIAGE_LEVELS = ("emergency", "clinic", "self_observe")
BASE_CONDITION = "B"
NULL_CONDITION = "C"
BASE_KIND = "base"
HI_KINDS = ("hi", "hi2")
# base 侧时限落在这档，说明档位金标准本身压在模糊地带
FUZZY_URGENCY = ("数天内",)
# hi 侧时限标到「立即」而档位只能给 clinic：档位量表的天花板，不是模型错误
CEILING_URGENCY = "立即"


@dataclass(frozen=True)
class CaseInfo:
    case_id: str
    family: str
    condition: str
    kind: str
    gold_triage: str
    urgency: str


def index_cases(path: Path) -> dict[str, CaseInfo]:
    cases: dict[str, CaseInfo] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        gold = row["gold"] or {}
        cases[str(row["case_id"])] = CaseInfo(
            case_id=str(row["case_id"]),
            family=str(row["family"]),
            condition=str(row["condition"]),
            kind=str(row["condition_kind"]),
            gold_triage=str(gold.get("triage", "")),
            urgency=str(row.get("urgency", "")),
        )
    return cases


def is_fuzzy(case: CaseInfo) -> bool:
    """边界模糊集成员判定（README 预注册规则 2、3、4）。"""
    if case.gold_triage == "self_observe" and case.urgency in FUZZY_URGENCY:
        return True
    return case.urgency == CEILING_URGENCY


def _tier(record: dict[str, object]) -> str | None:
    value = record.get("triage")
    return value if isinstance(value, str) and value in TRIAGE_LEVELS else None


def pair_outcome(base: str | None, hi: str | None, gold_base: str, gold_hi: str) -> str:
    """一对配对单元的结局，五类互斥：

    flip_gold         base 与 hi 都按各自金标准作答，背景被模型用到
    base_conservative base 答错（通常是答成门诊）、hi 答对——模型对一切偏保守，
                      hi 的答对不能记成「用了背景」（自我观察地板效应）
    hi_under          base 答对、hi 答错——背景被忽略
    both_off          两侧都错
    invalid           任何一侧没有合法档位
    """
    if base is None or hi is None:
        return "invalid"
    if base == gold_base and hi == gold_hi:
        return "flip_gold"
    if hi == gold_hi:
        return "base_conservative"
    if base == gold_base:
        return "hi_under"
    return "both_off"


@dataclass
class ArmSummary:
    arm: str
    model: str
    outcome: Counter[str] = field(default_factory=Counter)
    moved: Counter[str] = field(default_factory=Counter)
    null_matched: int = 0
    null_total: int = 0
    fuzzy_outcome: Counter[str] = field(default_factory=Counter)
    base_mismatch_urgency: Counter[str] = field(default_factory=Counter)

    @property
    def pairs(self) -> int:
        return sum(self.outcome.values())

    def rate(self, key: str, subset: Counter[str] | None = None) -> float:
        pool = subset if subset is not None else self.outcome
        total = sum(pool.values())
        return pool[key] / total if total else float("nan")


def collect(
    records: list[dict[str, object]], cases: dict[str, CaseInfo]
) -> tuple[list[ArmSummary], dict[str, Counter[str]]]:
    """聚合出（臂 × 模型）汇总与逐族明细。

    一个配对单元 = 同族同臂同模型同重复同变体下，base 条件与一个 hi 条件各一次
    调用；零孪生对照 = 同单元里 B 与 C 两次调用是否同档。变体进配对键：多变体
    运行时 V1 的 base 不会拿去配 V2 的 hi。
    """
    by_unit: dict[tuple[str, str, str, int, str], dict[str, str | None]] = defaultdict(dict)
    for record in records:
        case = cases.get(str(record["case_id"]))
        if case is None:
            continue
        unit = (
            str(record["arm"]),
            str(record["model"]),
            case.family,
            int(str(record["repetition"])),
            str(record.get("variant", "V1")),
        )
        by_unit[unit][case.condition] = _tier(record)

    arms: dict[tuple[str, str], ArmSummary] = {}
    per_family: dict[str, Counter[str]] = defaultdict(Counter)

    def summary_for(arm: str, model: str) -> ArmSummary:
        return arms.setdefault((arm, model), ArmSummary(arm=arm, model=model))

    for (arm, model, family, _rep, _variant), tiers in by_unit.items():
        fam_cases = {case.condition: case for case in cases.values() if case.family == family}
        base_case = fam_cases.get(BASE_CONDITION)
        if base_case is None or BASE_CONDITION not in tiers:
            continue
        base = tiers[BASE_CONDITION]
        rows = summary_for(arm, model)

        for condition, case in sorted(fam_cases.items()):
            if case.kind not in HI_KINDS or condition not in tiers:
                continue
            hi = tiers[condition]
            outcome = pair_outcome(base, hi, base_case.gold_triage, case.gold_triage)
            rows.outcome[outcome] += 1
            if base is not None and hi is not None:
                rows.moved["moved" if base != hi else "static"] += 1
            if is_fuzzy(base_case) or is_fuzzy(case):
                rows.fuzzy_outcome[outcome] += 1
            if base != base_case.gold_triage:
                rows.base_mismatch_urgency[base_case.urgency] += 1
            per_family[family][outcome] += 1

        if NULL_CONDITION in tiers and NULL_CONDITION in fam_cases:
            rows.null_total += 1
            null_tier = tiers[NULL_CONDITION]
            rows.null_matched += int(null_tier is not None and null_tier == base)

    ordered = [arms[key] for key in sorted(arms)]
    return ordered, dict(per_family)


def render(
    summaries: list[ArmSummary], per_family: dict[str, Counter[str]], cases: dict[str, CaseInfo]
) -> None:
    header = (
        "| 臂 | 模型 | 配对 | 翻转到位 | base保守 | 忽略背景 | 双错 | 无效 | 位移率 | 零孪生一致 |"
    )
    print(header)
    print("| --- " * 10 + "|")
    for row in summaries:
        print(
            f"| {row.arm} | {row.model} | {row.pairs} "
            f"| {row.rate('flip_gold'):.2f} | {row.rate('base_conservative'):.2f} "
            f"| {row.rate('hi_under'):.2f} | {row.rate('both_off'):.2f} "
            f"| {row.rate('invalid'):.2f} | "
            f"{row.moved['moved'] / max(1, row.moved['moved'] + row.moved['static']):.2f} "
            f"| {row.null_matched}/{row.null_total} |"
        )

    print("\n边界模糊集拆分（README 预注册规则 3）：")
    fuzzy_ids = sorted(case.case_id for case in cases.values() if is_fuzzy(case))
    print(f"模糊/天花板成员: {fuzzy_ids or '无'}")
    print("| 臂 | 模型 | 模糊配对 | 模糊内翻转 | 干净配对 | 干净内翻转 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in summaries:
        clean = row.outcome - row.fuzzy_outcome
        print(
            f"| {row.arm} | {row.model} | {sum(row.fuzzy_outcome.values())} "
            f"| {row.rate('flip_gold', row.fuzzy_outcome):.2f} "
            f"| {sum(clean.values())} | {row.rate('flip_gold', clean):.2f} |"
        )

    print("\nbase 被答错时的时限交叉（预注册规则 2，按 base 例的时限档计数）：")
    for row in summaries:
        print(f"- {row.arm} {row.model}: {dict(row.base_mismatch_urgency) or '无'}")

    print("\n逐族明细（跨臂跨模型合计）：")
    for family, counts in sorted(per_family.items()):
        total = sum(counts.values())
        print(
            f"- {family}: 配对 {total}，翻转 {counts['flip_gold']}，"
            f"base保守 {counts['base_conservative']}，忽略背景 {counts['hi_under']}，"
            f"双错 {counts['both_off']}，无效 {counts['invalid']}"
        )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("用法: uv run python -m analysis.families runs/<file>.jsonl [...]")
        return 1
    cases_path = Path(__file__).resolve().parent.parent / "cases" / "families.jsonl"
    records = dedupe([record for path in map(Path, args) for record in load(path)])
    cases = index_cases(cases_path)
    if not any(str(record["case_id"]) in cases for record in records):
        print("[warn] 记录里没有族病例，先确认跑的是 --cases families")
    summaries, per_family = collect(records, cases)
    render(summaries, per_family, cases)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
