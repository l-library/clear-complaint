"""跑实验矩阵：病例 × 变体 × 臂 × 模型 × 重复，逐格写 runs/ 下的 JSONL。

只追加、可续跑：已存在的 unit_id 跳过，中断后重跑不会重复烧配额。
并发受限于模型服务的限流，默认 4 路。

用法：
    uv run python -m tools.run_matrix --cases pilot --arms A0,Aall --reps 1 --models 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from harness import cases as case_lib
from harness import llm, pipeline, retrieval, vocab
from harness.arms import ARMS, arm

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE / "runs"


def _departments() -> list[str]:
    payload = json.loads((HERE / "corpus" / "departments.json").read_text(encoding="utf-8"))
    return [row["name"] for row in payload["departments"]]


def _done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        json.loads(line)["unit_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="pilot")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--models", type=int, default=2, help="取 BENCH 里前几个模型")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--tag", default="")
    args = parser.parse_args()

    arm_names = [name.strip() for name in args.arms.split(",") if name.strip()]
    models = list(llm.BENCH[: args.models])
    loaded = case_lib.load(HERE / "cases" / f"{args.cases}.jsonl")
    departments = _departments()
    known = vocab.known_terms()
    index = retrieval.Index()

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "cases": [c.case_id for c in loaded],
                "arms": {name: arm(name).snapshot() for name in arm_names},
                "models": models,
                "reps": args.reps,
                "corpus": index.meta.get("chunks_sha256"),
                "tag": args.tag,
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()[:8]
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"{args.cases}-{fingerprint}.jsonl"
    finished = _done(out)

    units = [
        (case, variant, arm_name, model, repetition)
        for case in loaded
        for variant in case_lib.VARIANTS
        for arm_name in arm_names
        for model in models
        for repetition in range(1, args.reps + 1)
    ]
    pending = [u for u in units if _unit_id(*u) not in finished]
    print(f"[info] 总计 {len(units)} 格，已完成 {len(finished)}，待跑 {len(pending)} → {out.name}")

    def work(unit: tuple[case_lib.Case, str, str, str, int]) -> str:
        case, variant, arm_name, model, repetition = unit
        record = pipeline.run_unit(
            case_id=case.case_id,
            variant=variant,
            arm_name=arm_name,
            model=model,
            repetition=repetition,
            raw_text=case.variants[variant],
            known_terms=known,
            departments=departments,
            index=index,
        )
        return pipeline.dump(record)

    started = time.monotonic()
    with (
        ThreadPoolExecutor(max_workers=args.workers) as pool,
        out.open("a", encoding="utf-8") as handle,
    ):
        for count, line in enumerate(pool.map(work, pending), 1):
            handle.write(line + "\n")
            handle.flush()
            if count % 10 == 0:
                print(f"[info] {count}/{len(pending)}  用时 {time.monotonic() - started:.0f}s")
    print(f"[info] 完成，写入 {out}")
    return 0


def _unit_id(case: case_lib.Case, variant: str, arm_name: str, model: str, repetition: int) -> str:
    return f"{case.case_id}-{variant}-{arm_name}-{model}-r{repetition}"


if __name__ == "__main__":
    raise SystemExit(main())
