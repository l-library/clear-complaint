"""随访复评的口径报告。

预注册口径，跑完不许改：

- 升级率：档位为 clinic 或 emergency 的比例。观察档复评后的正确动作：
  恶化 -> 升级；不变 -> 不动；好转 -> 维持或关闭（自我观察）。
- 方向敏感度：升级率（非红旗恶化） − 升级率（不变）。随访的模型侧价值全在这
  个差值上：等于零说明升级只能靠红旗确定性层。
- 好转承认率：好转方向上答出自我观察的比例。第一轮入口的对照是
  runs/families-*.jsonl 里 base 条件的自我观察使用率（约 6%）；若好转承认率
  显著高于它，说明地板部分来自单轮裁决，复评给了模型台阶。
- 红旗短路率：红旗恶化方向上 status=short_circuit 的比例。Aall 应为 1.0，
  A0 应为 0.0（该臂没有红旗层），两臂之差就是确定性层的贡献。

用法：
    uv run python -m analysis.followup runs/followup-*.jsonl [runs/families-*.jsonl]
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from analysis.metrics import dedupe, load

DIRECTIONS = ("better", "same", "worse_noflag", "worse_rf")
TRIAGE_LEVELS = ("emergency", "clinic", "self_observe")


def _tier(record: dict[str, object]) -> str | None:
    value = record.get("triage")
    return value if isinstance(value, str) and value in TRIAGE_LEVELS else None


def _direction(record: dict[str, object]) -> str | None:
    variant = str(record.get("variant", ""))
    if not variant.startswith("fu-"):
        return None
    return variant.removeprefix("fu-")


def collect(
    records: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, Counter[str]]]:
    table: dict[tuple[str, str], dict[str, Counter[str]]] = defaultdict(
        lambda: {name: Counter() for name in DIRECTIONS}
    )
    for record in records:
        direction = _direction(record)
        if direction not in DIRECTIONS:
            continue
        key = (str(record["arm"]), str(record["model"]))
        tier = _tier(record)
        table[key][direction][tier or "无效"] += 1
        if record.get("status") == "short_circuit":
            table[key][direction]["短路"] += 1
    return dict(table)


def _escalation(counts: Counter[str]) -> float:
    total = counts["self_observe"] + counts["clinic"] + counts["emergency"]
    if not total:
        return float("nan")
    return (counts["clinic"] + counts["emergency"]) / total


def render(
    table: dict[tuple[str, str], dict[str, Counter[str]]],
    entry: dict[tuple[str, str], Counter[str]],
) -> None:
    names = {
        "better": "好转",
        "same": "不变",
        "worse_noflag": "恶化（无红旗）",
        "worse_rf": "恶化（红旗）",
    }
    print("| 臂 | 模型 | 方向 | n | 自我观察 | 门诊 | 急诊 | 无效 | 升级率 | 短路 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for arm_name, model in sorted(table):
        for direction in DIRECTIONS:
            counts = table[(arm_name, model)][direction]
            if not sum(counts.values()):
                continue
            print(
                f"| {arm_name} | {model} | {names[direction]} "
                f"| {counts['self_observe'] + counts['clinic'] + counts['emergency']} "
                f"| {counts['self_observe']} | {counts['clinic']} | {counts['emergency']} "
                f"| {counts['无效']} | {_escalation(counts):.2f} | {counts['短路']} |"
            )

    print("\n方向敏感度（升级率差：非红旗恶化 − 不变）：")
    for arm_name, model in sorted(table):
        cells = table[(arm_name, model)]
        delta = _escalation(cells["worse_noflag"]) - _escalation(cells["same"])
        entry_rate = entry.get((arm_name, model), Counter())
        entry_total = sum(entry_rate.values()) or 1
        print(
            f"- {arm_name} {model}: {delta:+.2f}"
            f"（入口自我观察 {entry_rate['self_observe']}/{entry_total}）"
        )

    print("\n好转承认率（答出自我观察 / 合法档位总数）：")
    for arm_name, model in sorted(table):
        cells = table[(arm_name, model)]
        better = cells["better"]
        denom = better["self_observe"] + better["clinic"] + better["emergency"]
        print(f"- {arm_name} {model}: {better['self_observe']}/{denom}")


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        usage = (
            "用法: uv run python -m analysis.followup "
            "runs/followup-*.jsonl [入口 runs/families-*.jsonl]"
        )
        print(usage)
        return 1
    records = dedupe([record for path in map(Path, args) for record in load(path)])
    table = collect(records)

    entry: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for record in records:
        case_id = str(record["case_id"])
        variant = str(record.get("variant", ""))
        if not case_id.startswith("F") or not case_id.endswith("B") or variant != "V1":
            continue
        entry[(str(record["arm"]), str(record["model"]))][_tier(record) or "无效"] += 1

    render(table, dict(entry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
