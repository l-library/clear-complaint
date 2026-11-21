"""四张图，全部从 runs 的 JSONL 直接重算。

图不是手画的：换一批记录重跑就能得到新图，材料里的数字与图因此对得上。
中文字体用系统里的 Noto Sans CJK，没有就会退化成方框，所以启动时显式设置并检查。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analysis import metrics  # noqa: E402
from harness.cases import VARIANTS  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
TRIAGE_ORDER = ("emergency", "clinic", "self_observe")
TRIAGE_LABEL = {"emergency": "急诊", "clinic": "门诊", "self_observe": "自我观察"}
RANK = {"self_observe": 0, "clinic": 1, "emergency": 2}


def _level(record: dict[str, object]) -> str | None:
    """只认枚举内的档位，非法值一律当作没有档位，避免图表被脏值带崩。"""
    value = record.get("triage")
    return value if isinstance(value, str) and value in RANK else None


# 降级方向：按危险程度排序，最危险的（急诊判成自我观察）放最上面
DOWNGRADE_KINDS = (
    ("emergency", "self_observe"),
    ("emergency", "clinic"),
    ("clinic", "self_observe"),
)
KIND_LABEL = {
    ("emergency", "self_observe"): "急诊 → 自我观察",
    ("emergency", "clinic"): "急诊 → 门诊",
    ("clinic", "self_observe"): "门诊 → 自我观察",
}


def _setup_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans CJK SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _variant_heat(records: list[dict[str, object]]) -> None:
    arms = sorted({str(record["arm"]) for record in records})
    fig, axes = plt.subplots(1, len(arms), figsize=(4.2 * len(arms), 3.6), squeeze=False)
    for axis, arm_name in zip(axes[0], arms, strict=True):
        subset = [record for record in records if record["arm"] == arm_name]
        grid = np.full((len(VARIANTS), len(VARIANTS)), np.nan)
        # 行是变体，列是变体：格子表示「两变体档位相同的比例」，对角线天然为 1
        for row, left in enumerate(VARIANTS):
            for col, right in enumerate(VARIANTS):
                same = total = 0
                for case_id in {str(record["case_id"]) for record in subset}:
                    picks = {
                        str(record["variant"]): _level(record)
                        for record in subset
                        if record["case_id"] == case_id
                    }
                    if left in picks and right in picks and picks[left] and picks[right]:
                        total += 1
                        same += int(picks[left] == picks[right])
                grid[row, col] = same / total if total else np.nan
        image = axis.imshow(grid, vmin=0, vmax=1, cmap="RdYlGn")
        axis.set_xticks(range(len(VARIANTS)), VARIANTS)
        axis.set_yticks(range(len(VARIANTS)), VARIANTS)
        axis.set_title(f"{arm_name} 变体两两一致率")
        for row in range(len(VARIANTS)):
            for col in range(len(VARIANTS)):
                if not np.isnan(grid[row, col]):
                    axis.text(
                        col, row, f"{grid[row, col]:.2f}", ha="center", va="center", fontsize=8
                    )
        fig.colorbar(image, ax=axis, fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT / "variant-consistency.png", dpi=150)
    plt.close(fig)


def _main_bar(records: list[dict[str, object]]) -> None:
    rows = metrics.summary(records)
    labels, heights, errors = [], [], []
    for row in rows:
        values = metrics.per_case_delta(records, row.arm, "triage")
        low, high = metrics.cluster_bootstrap(values, rounds=2000)
        labels.append(f"{row.arm}\n{row.model}")
        heights.append(row.triage_consistency)
        errors.append(
            [max(0.0, row.triage_consistency - low), max(0.0, high - row.triage_consistency)]
        )

    fig, axis = plt.subplots(figsize=(6.5, 4))
    axis.bar(labels, heights, yerr=np.asarray(errors).T, capsize=6, color="#4C78A8")
    axis.set_ylim(0, 1.05)
    axis.set_ylabel("分诊档一致率（同臂内相对 V1）")
    axis.set_title("约束前后的分诊档一致率（95% 聚类 bootstrap 区间）")
    for index, value in enumerate(heights):
        axis.text(index, value + 0.03, f"{value:.2f}", ha="center")
    fig.tight_layout()
    fig.savefig(OUT / "triage-consistency.png", dpi=150)
    plt.close(fig)


def _confusion(records: list[dict[str, object]], gold: dict[str, str]) -> None:
    matrix = np.zeros((len(TRIAGE_ORDER), len(TRIAGE_ORDER)))
    for record in records:
        predicted = _level(record)
        truth = gold.get(str(record["case_id"]))
        if isinstance(predicted, str) and truth in TRIAGE_ORDER and predicted in TRIAGE_ORDER:
            matrix[TRIAGE_ORDER.index(truth)][TRIAGE_ORDER.index(predicted)] += 1

    fig, axis = plt.subplots(figsize=(4.6, 4))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(3), [TRIAGE_LABEL[key] for key in TRIAGE_ORDER])
    axis.set_yticks(range(3), [TRIAGE_LABEL[key] for key in TRIAGE_ORDER])
    axis.set_xlabel("模型给出的档位")
    axis.set_ylabel("金标准档位")
    axis.set_title("三档混淆矩阵")
    for row in range(3):
        for col in range(3):
            axis.text(col, row, int(matrix[row, col]), ha="center", va="center")
    fig.colorbar(image, ax=axis, fraction=0.046)
    fig.tight_layout()
    fig.savefig(OUT / "confusion.png", dpi=150)
    plt.close(fig)


def _case_card(records: list[dict[str, object]], gold: dict[str, str]) -> None:
    """案例卡：同一例的不同说法给出什么结论。答辩时最有说服力的一张。"""
    by_case: dict[str, dict[str, str]] = defaultdict(dict)
    for record in records:
        predicted = _level(record)
        if predicted:
            by_case[str(record["case_id"])][str(record["variant"])] = predicted
    moved = {
        case: picks
        for case, picks in by_case.items()
        if len({value for value in picks.values()}) > 1
    }
    chosen = next(iter(sorted(moved, key=lambda key: -len(moved[key]))), None)
    if chosen is None:
        return

    fig, axis = plt.subplots(figsize=(6.5, 2.6))
    axis.axis("off")
    truth = TRIAGE_LABEL.get(gold.get(chosen, ""), "—")
    lines = [f"病例 {chosen}（金标准：{truth}）"]
    for variant in VARIANTS:
        value = moved[chosen].get(variant)
        lines.append(
            f"{variant}: {TRIAGE_LABEL.get(value, '未给出')}" if value else f"{variant}: —"
        )
    axis.text(0.02, 0.95, "\n".join(lines), va="top", fontsize=11)
    axis.set_title("案例卡：同一个人，不同说法，不同结论")
    fig.tight_layout()
    fig.savefig(OUT / "case-card.png", dpi=150)
    plt.close(fig)


def _downgrade(records: list[dict[str, object]], arms: tuple[str, ...] = ("A0", "Aall")) -> None:
    """降级图：删减细节之后，判轻的是不是随机分布的。

    一致率只说「不一样」，不说「往哪个方向不一样」。把降级方向按病例摊开，
    才能看出信息缺失带来的是系统性的低判，而不是随机抖动。
    """
    fig, axes = plt.subplots(1, len(arms), figsize=(5.2 * len(arms), 4.2), squeeze=False)
    for axis, arm_name in zip(axes[0], arms, strict=True):
        subset = [record for record in records if record["arm"] == arm_name]
        baseline = {
            (record["case_id"], record["model"], record["repetition"]): record["triage"]
            for record in subset
            if record["variant"] == "V1"
        }
        counts: dict[str, dict[tuple[str, str], int]] = defaultdict(
            lambda: {kind: 0 for kind in DOWNGRADE_KINDS}
        )
        for record in subset:
            if record["variant"] == "V1":
                continue
            current = _level(record)
            base = baseline.get((record["case_id"], record["model"], record["repetition"]))
            if not isinstance(current, str) or not isinstance(base, str) or current == base:
                continue
            if RANK[current] < RANK[base]:
                counts[str(record["case_id"])][(base, current)] += 1

        cases = sorted(counts) or ["—"]
        left = np.zeros(len(cases))
        for kind in DOWNGRADE_KINDS:
            values = np.asarray([counts[case][kind] for case in cases], dtype=float)
            axis.barh(cases, values, left=left, label=KIND_LABEL[kind])
            left += values
        axis.set_title(f"{arm_name}：判轻的方向（相对 V1）")
        axis.set_xlabel("降级次数")
        axis.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "downgrade.png", dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()

    _setup_font()
    OUT.mkdir(parents=True, exist_ok=True)
    records = metrics.dedupe([record for path in args.runs for record in metrics.load(path)])
    cases_dir = Path(__file__).resolve().parent.parent / "cases"
    gold: dict[str, str] = {}
    for name in ("pilot.jsonl", "drafts.jsonl"):
        path = cases_dir / name
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                gold[row["case_id"]] = row["gold"]["triage"]

    _main_bar(records)
    _variant_heat(records)
    _confusion(records, gold)
    _case_card(records, gold)
    _downgrade(records)
    print(f"[info] 状态分布 {dict(Counter(str(r['status']) for r in records))}")
    print(f"[info] 图写入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
