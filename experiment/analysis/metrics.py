"""从 runs/ 的 JSONL 重算全部指标。

只读原始记录，不读任何中间缓存——这样「材料里的数字能用交付物复现」是可验证的，
而不是一句承诺。统计按病例做聚类的 bootstrap：同一例的五个变体高度相关，按格重采样
会把区间算窄。

用法：
    uv run python -m analysis.metrics runs/pilot-xxxxxxxx.jsonl
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from harness.cases import VARIANTS

BASELINE = "V1"
BOOTSTRAP_ROUNDS = 10_000
SEED = 20261201


@dataclass(frozen=True)
class Summary:
    arm: str
    model: str
    triage_consistency: float
    department_consistency: float
    units: int
    effective_units: int
    clarification_rate: float
    citation_pass_rate: float
    redflag_miss_rate: float


def load(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _triage(record: dict[str, object]) -> str | None:
    value = record.get("triage")
    return value if isinstance(value, str) else None


def _department(record: dict[str, object]) -> str | None:
    value = record.get("department")
    return value if isinstance(value, str) else None


def _names(record: dict[str, object]) -> list[str]:
    value = record.get("kept_conditions")
    return [str(item) for item in value] if isinstance(value, list) else []


def _deleted(record: dict[str, object]) -> int:
    value = record.get("deleted_count")
    return value if isinstance(value, int) else 0


def consistency(records: list[dict[str, object]], field: str) -> float:
    """同臂内，各变体与 V1 一致的比例。V1 与自己天然一致，不计入分母。"""
    pick = _triage if field == "triage" else _department
    groups: dict[tuple[str, str, str], dict[str, str | None]] = defaultdict(dict)
    for record in records:
        key = (str(record["arm"]), str(record["model"]), str(record["case_id"]))
        groups[key][str(record["variant"])] = pick(record)

    matched = total = 0
    for variants in groups.values():
        base = variants.get(BASELINE)
        if base is None:
            continue
        for variant in VARIANTS:
            if variant == BASELINE or variant not in variants:
                continue
            value = variants[variant]
            if value is None:
                continue
            total += 1
            matched += int(value == base)
    return matched / total if total else float("nan")


def per_case_delta(records: list[dict[str, object]], arm: str, field: str) -> dict[str, float]:
    """逐例的一致率，bootstrap 的重采样单位就是它。"""
    pick = _triage if field == "triage" else _department
    case_values: dict[str, list[float]] = defaultdict(list)
    groups: dict[tuple[str, str], dict[str, str | None]] = defaultdict(dict)
    for record in records:
        if record["arm"] != arm:
            continue
        key = (str(record["model"]), str(record["case_id"]))
        groups[key][str(record["variant"])] = pick(record)
    for (_, case_id), variants in groups.items():
        base = variants.get(BASELINE)
        if base is None:
            continue
        for variant in VARIANTS:
            if variant == BASELINE or variant not in variants:
                continue
            value = variants[variant]
            if value is None:
                continue
            case_values[case_id].append(1.0 if value == base else 0.0)
    return {case: sum(values) / len(values) for case, values in case_values.items() if values}


def cluster_bootstrap(
    values: dict[str, float], rounds: int = BOOTSTRAP_ROUNDS
) -> tuple[float, float]:
    """按病例重采样均值。返回 95% 置信区间。"""
    cases = sorted(values)
    if not cases:
        return float("nan"), float("nan")
    rng = random.Random(SEED)
    means = []
    for _ in range(rounds):
        sample = [values[cases[rng.randrange(len(cases))]] for _ in cases]
        means.append(sum(sample) / len(sample))
    means.sort()
    return means[int(0.025 * rounds)], means[int(0.975 * rounds)]


def summary(records: list[dict[str, object]]) -> list[Summary]:
    rows: list[Summary] = []
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        groups[(str(record["arm"]), str(record["model"]))].append(record)

    for (arm_name, model), subset in sorted(groups.items()):
        units = len(subset)
        with_triage = sum(1 for r in subset if _triage(r))
        clarification = sum(1 for r in subset if r.get("status") == "clarification")
        proposed = sum(len(_names(r)) + _deleted(r) for r in subset)
        kept = sum(len(_names(r)) for r in subset)
        misses = 0
        expected = 0
        for record in subset:
            if record.get("red_flags"):
                expected += 1
                misses += int(_triage(record) != "emergency")
        rows.append(
            Summary(
                arm=arm_name,
                model=model,
                triage_consistency=consistency(subset, "triage"),
                department_consistency=consistency(subset, "department"),
                units=units,
                effective_units=with_triage,
                clarification_rate=clarification / units if units else float("nan"),
                citation_pass_rate=kept / proposed if proposed else float("nan"),
                redflag_miss_rate=misses / expected if expected else 0.0,
            )
        )
    return rows


def main(path: Path) -> int:
    records = load(path)
    rows = summary(records)

    print(
        "| 臂 | 模型 | 片段数 | 有效率 | 档位一致率 | 科室一致率 | 澄清率 | 引用通过 | 红旗漏检 |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        print(
            f"| {row.arm} | {row.model} | {row.units} | {row.effective_units / row.units:.2f} | "
            f"{row.triage_consistency:.2f} | {row.department_consistency:.2f} | "
            f"{row.clarification_rate:.2f} | {row.citation_pass_rate:.2f} | "
            f"{row.redflag_miss_rate:.2f} |"
        )

    for row in rows:
        values = per_case_delta(records, row.arm, "triage")
        low, high = cluster_bootstrap(values)
        print(
            f"[ci] {row.arm} {row.model} 档位一致率 95% CI "
            f"[{low:.2f}, {high:.2f}]（{len(values)} 例）"
        )
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(Path(sys.argv[1])))
