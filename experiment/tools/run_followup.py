"""随访复评实验的第二轮调用。

背景：模型单轮几乎不给自我观察（base 保守 0.71–0.92），产品的对策是把观察档
做成带复评的流程——轻症无红旗进观察，复评文本重跑完整管线，恶化升级。本实验测
两件事：

1. 恶化方向能不能升级。红旗恶化应走确定性短路（不经过模型）；非红旗恶化只能
   靠模型对「比上次重了」的方向敏感。
2. 不变 / 好转方向稳不稳。不变的复评不该乱升档；好转的复评应该敢给自我观察。

第一轮入口档位不重复烧配额：对照读 runs/families-*.jsonl 的 base 条件记录。
复评材料在 cases/followup_scripts.jsonl（六族 × 四方向），红旗预期逐条预检，
不通过不开跑。第一轮主诉作为【既往就诊记录】进第二轮提示词，不带当时的档位
建议——避免锚定，方向敏感度的测量才干净。

用法：
    uv run python -m tools.run_followup --arms A0,Aall --reps 3 --models 2 --tag full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

from harness import cases as case_lib
from harness import llm, pipeline, redflag, retrieval, vocab
from harness.arms import ARMS, arm
from tools.run_matrix import Throttle, _departments, _done, _portrait

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE / "runs"
CASES = HERE / "cases"


def load_scripts(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_scripts(scripts: list[dict[str, object]]) -> list[str]:
    """红旗预期逐条预检：带红旗的恶化必须命中预期规则，其余一条都不许命中。"""
    problems: list[str] = []
    for row in scripts:
        hits = sorted(hit.rule_id for hit in redflag.detect(str(row["message"])))
        wanted = sorted(str(item) for item in cast("list[str]", row["expected_rf"]))
        if row["direction"] == "worse_rf" and hits != wanted:
            problems.append(f"{row['family']} worse_rf 命中 {hits}，预期 {wanted}")
        if row["direction"] != "worse_rf" and hits:
            problems.append(f"{row['family']} {row['direction']} 不应命中却命中 {hits}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", default="A0,Aall")
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--models", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--families", default="", help="只跑指定族（小样用），如 F01,F04")
    parser.add_argument("--temperature", type=float, default=llm.TEMPERATURE)
    parser.add_argument("--tag", default="")
    parsed = parser.parse_args(args)

    scripts = load_scripts(CASES / "followup_scripts.jsonl")
    problems = check_scripts(scripts)
    if problems:
        for problem in problems:
            print(f"[fail] {problem}")
        return 1
    print("[ok] 红旗预期 24 条预检通过")
    if parsed.families:
        wanted = {item.strip() for item in parsed.families.split(",") if item.strip()}
        scripts = [row for row in scripts if row["family"] in wanted]
        print(f"[info] 只跑 {sorted(wanted)}，共 {len(scripts)} 条材料")

    arm_names = [item.strip() for item in parsed.arms.split(",") if item.strip()]
    for name in arm_names:
        if name not in ARMS:
            print(f"[error] 未知实验臂: {name}")
            return 1
    models = list(llm.BENCH[: parsed.models])
    for model in models:
        try:
            llm.chat(model, [{"role": "user", "content": "回一个字：好"}], max_tokens=64)
        except llm.LLMError as exc:
            print(f"[error] {model} 预检失败：{exc}")
            return 1
        print(f"[info] {model} 预检通过")

    base = {case.case_id: case for case in case_lib.load(CASES / "families.jsonl")}
    departments = _departments()
    known = vocab.known_terms()
    index = retrieval.Index()

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "scripts": hashlib.sha256(
                    (CASES / "followup_scripts.jsonl").read_bytes()
                ).hexdigest(),
                "scripts_ids": [str(row["case_id"]) + str(row["direction"]) for row in scripts],
                "arms": {name: arm(name).snapshot() for name in arm_names},
                "models": models,
                "reps": parsed.reps,
                "corpus": index.meta.get("chunks_sha256"),
                "rules": hashlib.sha256(
                    (HERE / "corpus" / "red_flags.json").read_bytes()
                ).hexdigest(),
                "normalize": hashlib.sha256(
                    (HERE / "harness" / "normalize.py").read_bytes()
                ).hexdigest(),
                "cases": hashlib.sha256((CASES / "families.jsonl").read_bytes()).hexdigest(),
                "max_tokens": llm.MAX_TOKENS,
                "temperature": parsed.temperature,
                "tag": parsed.tag,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:8]
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"followup-{fingerprint}.jsonl"
    finished = _done(out)

    def unit_id_for(row: dict[str, object], arm_name: str, model: str, repetition: int) -> str:
        return pipeline.unit_id(
            f"{row['case_id']}-FU",
            f"fu-{row['direction']}",
            arm_name,
            model,
            repetition,
            parsed.temperature,
        )

    pending = [
        (row, arm_name, model, repetition)
        for row in scripts
        for arm_name in arm_names
        for model in models
        for repetition in range(1, parsed.reps + 1)
        if unit_id_for(row, arm_name, model, repetition) not in finished
    ]
    total = len(scripts) * len(arm_names) * len(models) * parsed.reps
    print(f"[info] 总计 {total} 格，已完成 {len(finished)}，待跑 {len(pending)} → {out.name}")

    throttle = Throttle(parsed.workers)

    def call(model: str, messages: list[dict[str, str]]) -> llm.Completion:
        return llm.chat(model, messages, temperature=parsed.temperature)

    def work(item: tuple[dict[str, object], str, str, int]) -> str:
        row, arm_name, model, repetition = item
        case = base[str(row["case_id"])]
        # 第一轮主诉进上下文，不带当时的档位建议，避免锚定方向敏感度测量
        context = f"上次主诉：{case.variants['V1']}；当时未命中红旗。"
        throttle.wait()
        record = pipeline.run_unit(
            case_id=f"{row['case_id']}-FU",
            variant=f"fu-{row['direction']}",
            arm_name=arm_name,
            model=model,
            repetition=repetition,
            raw_text=str(row["message"]),
            history=context,
            portrait=_portrait(case),
            known_terms=known,
            departments=departments,
            index=index,
            call=call,
            temperature=parsed.temperature,
        )
        return pipeline.dump(record)

    with (
        ThreadPoolExecutor(max_workers=parsed.workers) as pool,
        out.open("a", encoding="utf-8") as handle,
    ):
        for count, line in enumerate(pool.map(work, pending), 1):
            handle.write(line + "\n")
            handle.flush()
            if count % 20 == 0:
                print(f"[info] {count}/{len(pending)}")
    print(f"[ok] 写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
