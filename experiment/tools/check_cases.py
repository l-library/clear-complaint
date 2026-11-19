"""审稿用的病例检查：结构、金标准缺失、变体一致性启发式。

drafts.jsonl 里的金标准是 null（要人来标），所以不能走 harness.cases.load，
那套校验要求金标准齐全。这里只做「审稿时想看的东西」：结构是否成立、五个变体
是否真的只改了表述。

用法：
    uv run python -m tools.check_cases cases/drafts.jsonl
    uv run python -m tools.check_cases cases/pilot.jsonl --final
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path

from harness import redflag

VARIANTS = ("V1", "V2", "V3", "V4", "V5")
TRIAGE = ("emergency", "clinic", "self_observe")

# 变体与它该有的标记。缺了标记说明这一版没改到点子上，多了标记说明改了内容。
MARKERS = {
    # 自我诊断不一定要以「我觉得」开头：把病名挂在句尾问出来也是自我归因
    "V2": (
        "我好像",
        "我觉得",
        "我怀疑",
        "我估计",
        "可能是",
        "应该是",
        "估计是",
        "是不是",
        "会不会是",
        "怕是",
    ),
    "V3": ("害怕", "担心", "着急", "紧张", "烦", "会不会", "严重"),
}
# 病程或起病时点都算：数字加单位要认「两个小时」，也要认「早上」「刚才」这类锚点
DURATION = re.compile(
    r"(\d+|[一二三四五六七八九十两半几]+)\s*个?\s*(天|周|小时|分钟|月|年)"
    r"|早上|上午|中午|下午|傍晚|晚上|夜里|昨天|前天|今天|刚才|半小时"
)
SPELLED_DIGITS = re.compile(r"[a-zA-Z]{2,}")


def _issues(row: Mapping[str, object]) -> list[str]:
    problems: list[str] = []
    variants = row.get("variants")
    if not isinstance(variants, dict):
        return ["缺少 variants"]

    missing = [name for name in VARIANTS if name not in variants]
    if missing:
        problems.append(f"缺变体 {missing}")
        return problems

    texts = {name: str(variants[name]) for name in VARIANTS}
    if len(set(texts.values())) < len(VARIANTS):
        problems.append("有两段变体文字完全相同")

    # V1 是基线，必须自带病程，否则 V4 删无可删
    if not DURATION.search(texts["V1"]):
        problems.append("V1 没有病程，V4 无从删减")
    # V4 必须删掉病程与细节
    if DURATION.search(texts["V4"]):
        problems.append("V4 还带着病程细节")
    if len(texts["V4"]) >= len(texts["V1"]) * 0.8:
        problems.append("V4 与 V1 长度接近，可能没删够")

    for name, markers in MARKERS.items():
        has_marker = any(marker in texts[name] for marker in markers)
        if not has_marker:
            problems.append(f"{name} 缺少该有的标记（归因或情绪）")
        # V1/V4 不该出现归因或情绪，否则对照组被污染
    for name in ("V1", "V4"):
        if any(marker in texts[name] for marker in MARKERS["V2"] + MARKERS["V3"]):
            problems.append(f"{name} 掺进了归因或情绪，污染基线")

    # V5 只改写法：应当出现拼音或与 V1 明显不同的字形，但实词不能换
    if not SPELLED_DIGITS.search(texts["V5"]):
        problems.append("V5 没有口语或拼音改写")

    gold = row.get("gold")
    if gold is None:
        problems.append("金标准待标（draft）")
    elif isinstance(gold, dict):
        if gold.get("triage") not in TRIAGE:
            problems.append(f"档位非法 {gold.get('triage')}")
        if not gold.get("department"):
            problems.append("缺首诊科室")
        else:
            expected = gold.get("red_flags")
            if isinstance(expected, list) and expected:
                fired = {hit.rule_id for text in texts.values() for hit in redflag.detect(text)}
                missed = sorted(set(str(item) for item in expected) - fired)
                if missed:
                    problems.append(
                        f"金标准红旗 {missed} 在五个变体里都命不中"
                        "（要么补触发词，要么这例不该标这条红旗）"
                    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--final", action="store_true", help="要求金标准已填")
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    broken = 0
    for number, line in enumerate(args.path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            broken += 1
            print(f"[FAIL] 第 {number} 行 JSON 语法错误：{exc.msg}（第 {exc.colno} 列）")
            print(f"       {line[max(0, exc.colno - 50) : exc.colno + 50]}")
    blockers = 0
    for row in rows:
        problems = _issues(row)
        if args.final:
            problems = [item for item in problems if "待标" not in item]
        level = "FAIL" if problems and not all("待标" in item for item in problems) else "ok"
        if level == "FAIL":
            blockers += 1
        detail = "；".join(problems) if problems else "—"
        print(f"[{level:4}] {row.get('case_id', '?'):5} {row.get('domain', ''):10} {detail}")

    drafts = sum(1 for row in rows if row.get("gold") is None)
    print(
        f"\n共 {len(rows) + broken} 行，可解析 {len(rows)} 例，金标准待标 {drafts} 例，"
        f"结构问题 {blockers} 例，JSON 坏行 {broken} 行"
    )
    return 1 if blockers or broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
