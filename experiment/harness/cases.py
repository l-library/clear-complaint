"""病例与变体的载入与校验。

一例 = 主诉文本 + 画像 + 五个变体 + 金标准。画像在各变体之间**必须完全一致**，
否则变体等价性当场破产：变动的就不只是表述了。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "corpus"
CASES = Path(__file__).resolve().parent.parent / "cases"

VARIANTS = ("V1", "V2", "V3", "V4", "V5")
TRIAGE_LEVELS = ("emergency", "clinic", "self_observe")
AGE_BANDS = ("<14", "14-64", ">=65")


@dataclass(frozen=True)
class Portrait:
    age_band: str
    sex: str
    pregnancy: bool
    history: str
    allergy: str


@dataclass(frozen=True)
class Gold:
    triage: str
    department: str
    red_flags: tuple[str, ...]


@dataclass(frozen=True)
class Case:
    case_id: str
    domain: str
    portrait: Portrait
    gold: Gold
    variants: dict[str, str]


def _departments() -> set[str]:
    payload = json.loads((CORPUS / "departments.json").read_text(encoding="utf-8"))
    return {row["name"] for row in payload["departments"]}


def load(path: Path | None = None) -> list[Case]:
    path = path or CASES / "pilot.jsonl"
    departments = _departments()
    cases: list[Case] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        portrait = Portrait(**row["portrait"])
        gold = Gold(**{**row["gold"], "red_flags": tuple(row["gold"]["red_flags"])})
        case = Case(
            case_id=row["case_id"],
            domain=row["domain"],
            portrait=portrait,
            gold=gold,
            variants=dict(row["variants"]),
        )
        _validate(case, departments)
        cases.append(case)
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("case_id 重复")
    return cases


def _validate(case: Case, departments: set[str]) -> None:
    if set(case.variants) != set(VARIANTS):
        raise ValueError(f"{case.case_id}: 变体不齐，需要 {VARIANTS}")
    if case.gold.triage not in TRIAGE_LEVELS:
        raise ValueError(f"{case.case_id}: 金标准档位非法 {case.gold.triage}")
    if case.gold.department not in departments:
        raise ValueError(f"{case.case_id}: 科室不在受控表 {case.gold.department}")
    if case.portrait.age_band not in AGE_BANDS:
        raise ValueError(f"{case.case_id}: 年龄段非法 {case.portrait.age_band}")
    # V4 删掉细节，就不该还带着病程；这条一致性也顺带把「变体改的是内容」挡在门外
    if any(cue in case.variants["V4"] for cue in ("天", "周", "小时")):
        raise ValueError(f"{case.case_id}: V4 应删掉病程细节")
