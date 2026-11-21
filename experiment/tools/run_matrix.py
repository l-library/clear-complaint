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
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from harness import cases as case_lib
from harness import llm, pipeline, retrieval, vocab
from harness.arms import ARMS, arm
from harness.retrieval import Index
from tools import domains

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE / "runs"


def _departments() -> list[str]:
    payload = json.loads((HERE / "corpus" / "departments.json").read_text(encoding="utf-8"))
    return [row["name"] for row in payload["departments"]]


def _done(path: Path) -> set[str]:
    """已完成单元。进程被强杀时最后一行可能是半截，跳过它继续续跑，而不是整轮崩掉。"""
    if not path.exists():
        return set()
    done: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            print("[warn] 跳过一行不完整的记录（上次中断留下的）")
            continue
        # api_error 是可重试的失败（限流、网关抖动），不算完成；其余状态都算
        if row.get("status") == "api_error":
            continue
        done.add(str(row["unit_id"]))
    return done


class Throttle:
    """按令牌桶限制单元启动速率，防止瞬时并发打满网关的吞吐配额。"""

    def __init__(self, workers: int, min_interval: float = 1.2) -> None:
        self._interval = min_interval / max(1, workers)
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self._interval
        if delay > 0:
            time.sleep(delay)


def _complaint(case: case_lib.Case, variant: str) -> str:
    """记忆与体征变体只换附加区块，主诉一律用 V1。"""
    if variant in case_lib.HISTORY_VARIANTS or variant in case_lib.VITALS_VARIANTS:
        return case.variants["V1"]
    return case.variants[variant]


def _portrait(case: case_lib.Case) -> str:
    """画像进提示词：年龄、性别、基础病、过敏史。四个臂一致。"""
    p = case.portrait
    age = {"<14": "14 岁以下", "14-64": "14 至 64 岁", ">=65": "65 岁及以上"}[p.age_band]
    return f"{age} · {p.sex} · {p.history} · {p.allergy}"


def _history(case: case_lib.Case, variant: str) -> str | None:
    if variant in case_lib.HISTORY_VARIANTS:
        return case.history.get(variant[-1])
    return None


def _vitals(case: case_lib.Case, variant: str) -> str | None:
    if variant in case_lib.VITALS_VARIANTS:
        return case.vitals.get(variant[-1])
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="pilot")
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--models", type=int, default=2, help="取 BENCH 里前几个模型")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--variants", default=",".join(case_lib.VARIANTS + case_lib.HISTORY_VARIANTS)
    )
    parser.add_argument("--temperature", type=float, default=llm.TEMPERATURE)
    parser.add_argument(
        "--pool",
        default="normal",
        choices=("normal", "irrelevant", "empty"),
        help="normal 走真实检索；irrelevant 换成无关片段；empty 不给任何依据",
    )
    parser.add_argument("--tag", default="")
    args = parser.parse_args()

    arm_names = [name.strip() for name in args.arms.split(",") if name.strip()]
    variants = [name.strip() for name in args.variants.split(",") if name.strip()]
    models = list(llm.BENCH[: args.models])

    # 起跑预检：上一次 glm-5.2 跑到一半被冻结（403 ModelArts.81006），
    # 720 格全部烧成 api_error 才发现。先各打一次，不通就别开跑。
    for model in models:
        try:
            llm.chat(model, [{"role": "user", "content": "回一个字：好"}], max_tokens=64)
        except llm.LLMError as exc:
            print(f"[error] {model} 预检失败：{exc}")
            return 1
        print(f"[info] {model} 预检通过")
    loaded = case_lib.load(HERE / "cases" / f"{args.cases}.jsonl")
    departments = _departments()
    known = vocab.known_terms()
    index = retrieval.Index()

    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "cases": [c.case_id for c in loaded],
                # 病例文本本身也要进指纹：改写某个变体而 case_id 不变时，
                # 只按 id 算指纹会让重跑把新文本的格子当成"已完成"跳过
                "cases_sha": hashlib.sha256(
                    (HERE / "cases" / f"{args.cases}.jsonl").read_bytes()
                ).hexdigest(),
                "variants": variants,
                "arms": {name: arm(name).snapshot() for name in arm_names},
                "models": models,
                "reps": args.reps,
                "corpus": index.meta.get("chunks_sha256"),
                "vocab": hashlib.sha256((HERE / "corpus" / "vocab.json").read_bytes()).hexdigest(),
                # 红旗规则改了，短路判定就变了；不算进指纹会让重跑把旧格子当成已完成
                "rules": hashlib.sha256(
                    (HERE / "corpus" / "red_flags.json").read_bytes()
                ).hexdigest(),
                "max_tokens": llm.MAX_TOKENS,
                "temperature": args.temperature,
                "pool": args.pool,
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
        for variant in variants
        for arm_name in arm_names
        for model in models
        for repetition in range(1, args.reps + 1)
    ]
    pending = [
        u
        for u in units
        if pipeline.unit_id(u[0].case_id, u[1], u[2], u[3], u[4], args.temperature) not in finished
    ]
    print(f"[info] 总计 {len(units)} 格，已完成 {len(finished)}，待跑 {len(pending)} → {out.name}")

    class Frozen(RuntimeError):
        """资源被冻结时继续跑只会把剩余格子烧成错误记录，直接中止。"""

    def pool_for(case: case_lib.Case) -> Index | retrieval.FixedPool:
        if args.pool == "normal":
            return index
        if args.pool == "empty":
            return retrieval.FixedPool([])
        others = [
            passage
            for passage in index.passages()
            if domains.hits(passage.text) and case.domain not in domains.hits(passage.text)
        ]
        start = sum(ord(ch) for ch in case.case_id) % max(1, len(others) - 5)
        return retrieval.FixedPool(others[start : start + 5])

    def call(model: str, messages: list[dict[str, str]]) -> llm.Completion:
        return llm.chat(model, messages, temperature=args.temperature)

    # 网关按吞吐限流：短探针测不出来，连续全量才撞。单元间强制间隔，宁可慢也不重跑
    throttle = Throttle(args.workers)

    def work(unit: tuple[case_lib.Case, str, str, str, int]) -> str:
        case, variant, arm_name, model, repetition = unit
        throttle.wait()
        record = pipeline.run_unit(
            case_id=case.case_id,
            variant=variant,
            arm_name=arm_name,
            model=model,
            repetition=repetition,
            raw_text=_complaint(case, variant),
            history=(
                case.history.get(variant[-1]) if variant in case_lib.HISTORY_VARIANTS else None
            ),
            known_terms=known,
            departments=departments,
            index=pool_for(case),
            call=call,
            temperature=args.temperature,
            pool=args.pool,
        )
        if record.status == "api_error" and "frozen" in record.draft_raw.lower():
            raise Frozen(f"{model}: {record.draft_raw[:120]}")
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
    tokens = 0
    for line in out.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        tokens += int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0)
    print(f"[info] 完成，写入 {out}；已记录 {tokens} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
