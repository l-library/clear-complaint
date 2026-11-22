"""生成阶段二验收用的冻结样本与约束规格书底稿。

冻结样本取阶段一实测结果里的众数：同一病例同一变体，在两个模型、三次重复下的
多数档位与多数科室，并记录一致度。阶段二在平台上重建约束之后，拿这份样本对照，
掉到阈值以下就说明平台侧实现不复现阶段一的结论。

用法：uv run python -m tools.build_handoff
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE / "runs"
CASES = HERE / "cases"
HANDOFF = HERE / "handoff"

# 阶段二验收阈值。由阶段一实测天花板反推：全约束臂的四臂配对一致率是
# 档位 0.913、科室 0.827，说明实现自身在理想条件下只能到这个量级。
# 平台重建低于 0.85 / 0.75，差异就不能再归因于噪声。
TRIAGE_THRESHOLD = 0.85
DEPARTMENT_THRESHOLD = 0.75

# 平台侧要复现的是主矩阵：五个变体族。记忆与体征变体属于可选项。
MAIN_VARIANTS = ("V1", "V2", "V3", "V4", "V5")


class Portrait(TypedDict):
    age_band: str
    sex: str
    pregnancy: bool
    history: str
    allergy: str


class CaseRow(TypedDict):
    case_id: str
    portrait: Portrait
    variants: dict[str, str]


@dataclass(frozen=True)
class Expected:
    case_id: str
    variant: str
    complaint: str
    portrait: str
    expected_triage: str
    expected_department: str
    agreement: float
    samples: int


def _level(record: dict[str, object]) -> str | None:
    value = record.get("triage")
    return value if value in {"emergency", "clinic", "self_observe"} else None


def _portrait(raw: CaseRow) -> str:
    p = raw["portrait"]
    age = {"<14": "14 岁以下", "14-64": "14 至 64 岁", ">=65": "65 岁及以上"}[p["age_band"]]
    return f"{age} · {p['sex']} · {p['history']} · {p['allergy']}"


def _cases() -> dict[str, CaseRow]:
    out: dict[str, CaseRow] = {}
    for name in ("pilot.jsonl", "drafts.jsonl"):
        for line in (CASES / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row: CaseRow = json.loads(line)
                out[row["case_id"]] = row
    return out


def _runs() -> list[dict[str, object]]:
    """只用当前这一代记录：同济网关、有画像、全约束臂。"""
    rows: list[dict[str, object]] = []
    for path in sorted(RUNS.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("arm") != "Aall":
                continue
            params = record.get("params") or {}
            if params.get("temperature", 0.7) != 0.7 or params.get("pool", "normal") != "normal":
                continue
            if record.get("corpus_sha", "") == "":
                continue
            rows.append(record)
    # 同一 unit_id 只留最后一条
    by_id = {str(row["unit_id"]): row for row in rows}
    return list(by_id.values())


def main() -> int:
    cases = _cases()
    latest: dict[str, dict[str, object]] = {}
    for record in _runs():
        model = str(record.get("model", ""))
        if not model.startswith(("DeepSeek", "GLM")):
            continue
        latest[str(record["unit_id"])] = record

    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in latest.values():
        variant = str(record.get("variant"))
        if variant in MAIN_VARIANTS:
            groups[(str(record["case_id"]), variant)].append(record)

    expected: list[Expected] = []
    for (case_id, variant), group in sorted(groups.items()):
        levels = [lv for r in group if (lv := _level(r))]
        statuses = Counter(str(r.get("status")) for r in group)
        # 多数单元没有档位时，预期行为就是澄清，而不是给出一个档位
        if not levels or statuses.most_common(1)[0][0] == "clarification":
            expected.append(
                Expected(
                    case_id=case_id,
                    variant=variant,
                    complaint=str(cases[case_id]["variants"][variant]),
                    portrait=_portrait(cases[case_id]),
                    expected_triage="clarification",
                    expected_department="",
                    agreement=round(statuses.most_common(1)[0][1] / len(group), 3),
                    samples=len(group),
                )
            )
            continue
        departments = [str(r["department"]) for r in group if r.get("department")]
        triage = Counter(levels).most_common(1)[0][0]
        triage_n = Counter(levels).most_common(1)[0][1]
        department = Counter(departments).most_common(1)[0][0] if departments else ""
        expected.append(
            Expected(
                case_id=case_id,
                variant=variant,
                complaint=str(cases[case_id]["variants"][variant]),
                portrait=_portrait(cases[case_id]),
                expected_triage=triage,
                expected_department=department,
                agreement=round(triage_n / len(group), 3),
                samples=len(group),
            )
        )

    HANDOFF.mkdir(parents=True, exist_ok=True)
    with (HANDOFF / "frozen_sample.jsonl").open("w", encoding="utf-8") as handle:
        for item in expected:
            handle.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")

    per_case: dict[str, list[Expected]] = defaultdict(list)
    for item in expected:
        per_case[item.case_id].append(item)
    full = sum(1 for rows in per_case.values() if len(rows) == len(MAIN_VARIANTS))
    weak = [item for item in expected if item.agreement < 0.8]
    print(f"[info] 冻结样本 {len(expected)} 条，覆盖 {len(per_case)} 例（五个变体齐全 {full} 例）")
    print(f"[info] 一致度低于 0.8 的条目 {len(weak)} 条")
    print(f"[info] 阈值：档位 {TRIAGE_THRESHOLD}，科室 {DEPARTMENT_THRESHOLD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
