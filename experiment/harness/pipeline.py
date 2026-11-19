"""跑一个实验单元：输入一条病例的一个变体，按某个臂产出可写进 runs/ 的记录。

顺序照着 docs/stage1.md：归一化 → 归因摘除（按臂）→ 红旗短路 → 检索 → 模型出草稿
→ 引用闸门与模板校验 → 档位与科室。红旗命中就直接短路，不调模型——那既是安全要求，
也省掉一次调用。
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from harness import arms, citation, llm, redflag, vocab
from harness.normalize import normalize, split_attribution
from harness.retrieval import Index

# 澄清先行的判据：主诉里有没有交代病程。没有病程就无从判断急缓，必须追问。
# 判据保持可解释、可复现，不假装能测出「部位、性质」这些更细的字段。
DURATION_CUES = (
    "天",
    "周",
    "小时",
    "分钟",
    "钟头",
    "个月",
    "年",
    "昨天",
    "前天",
    "今天",
    "刚才",
    "最近",
    "半天",
)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.MULTILINE)

LLMCall = Callable[[str, list[dict[str, str]]], llm.Completion]


@dataclass
class Record:
    unit_id: str
    case_id: str
    variant: str
    arm: str
    model: str
    repetition: int
    raw_text: str
    normalized_text: str = ""
    attribution: str | None = None
    red_flags: list[str] = field(default_factory=list)
    passage_ids: list[str] = field(default_factory=list)
    draft_raw: str = ""
    draft: dict[str, object] | None = None
    triage: str | None = None
    department: str | None = None
    kept_conditions: list[str] = field(default_factory=list)
    free_names: list[str] = field(default_factory=list)
    deleted_count: int = 0
    empty_after_gate: bool = False
    template_ok: bool = False
    status: str = "ok"
    reasoning_tokens: int = 0
    latency_ms: int = 0
    arm_hash: str = ""
    corpus_sha: str = ""
    params: dict[str, float | int] = field(default_factory=dict)


def parse_draft(text: str) -> dict[str, object] | None:
    """容忍代码块围栏，不做别的修补。修不好的算 parse_error，不重跑。"""
    cleaned = _FENCE.sub("", text).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _template_ok(payload: dict[str, object]) -> bool:
    triage = payload.get("triage")
    department = payload.get("department")
    conditions = payload.get("conditions")
    preparation = payload.get("preparation")
    return bool(
        triage and department and isinstance(conditions, list) and conditions and preparation
    )


def _missing_duration(text: str) -> bool:
    folded = normalize(text)
    return not any(cue in folded for cue in DURATION_CUES)


def run_unit(
    *,
    case_id: str,
    variant: str,
    arm_name: str,
    model: str,
    repetition: int,
    raw_text: str,
    known_terms: set[str],
    departments: list[str],
    index: Index,
    call: LLMCall = llm.chat,
) -> Record:
    current = arms.arm(arm_name)
    record = Record(
        unit_id=f"{case_id}-{variant}-{arm_name}-{model}-r{repetition}",
        case_id=case_id,
        variant=variant,
        arm=arm_name,
        model=model,
        repetition=repetition,
        raw_text=raw_text,
        normalized_text=normalize(raw_text),
        arm_hash=current.snapshot(),
        corpus_sha=str(getattr(index, "meta", {}).get("chunks_sha256", ""))[:16],
        params={
            "temperature": llm.TEMPERATURE,
            "top_p": llm.TOP_P,
            "max_tokens": llm.MAX_TOKENS,
        },
    )

    complaint = raw_text
    if current.strip_attribution:
        complaint, record.attribution = split_attribution(raw_text, known_terms)

    # 红旗优先于澄清追问：安全先于补字段
    if current.redflag:
        hits = redflag.detect(raw_text)
        record.red_flags = [hit.rule_id for hit in hits]
        if hits:
            record.status = "short_circuit"
            record.triage = "emergency"
            record.department = "急诊科"
            return record

    if current.clarify_first and _missing_duration(complaint):
        record.status = "clarification"
        return record

    passages = index.search(complaint, k=5)
    record.passage_ids = [passage.chunk_id for passage in passages]
    messages = arms.build_messages(
        arm_name,
        departments,
        [(position, passage.text) for position, passage in enumerate(passages)],
        complaint,
        sorted(vocab.known_terms() - {"未标注"}),
    )

    started = time.monotonic()
    try:
        completion = call(model, messages)
    except llm.LLMError as exc:
        record.status = "api_error"
        record.draft_raw = str(exc)[:500]
        record.latency_ms = int((time.monotonic() - started) * 1000)
        return record

    record.draft_raw = completion.content
    record.reasoning_tokens = completion.reasoning_tokens
    record.latency_ms = completion.latency_ms
    record.draft = parse_draft(completion.content)
    if record.draft is None:
        record.status = "parse_error"
        return record

    payload = record.draft
    triage = payload.get("triage")
    department = payload.get("department")
    record.triage = triage if isinstance(triage, str) else None
    record.department = department if isinstance(department, str) else None
    record.template_ok = _template_ok(payload)
    if current.output_side_instruction and not record.template_ok:
        record.status = "template_invalid"
        return record

    if current.citation_gate:
        raw_conditions = payload.get("conditions")
        conditions = [
            citation.Condition(
                name=str(item.get("name", "")),
                evidence_idx=[int(index_) for index_ in item.get("evidence_idx") or []],
                quote=str(item.get("quote", "")),
            )
            for item in (raw_conditions if isinstance(raw_conditions, list) else [])
            if isinstance(item, dict)
        ]
        gate = citation.verify(conditions, [passage.text for passage in passages])
        record.deleted_count = gate.deleted_count
        # 引文核得上还要落在受控词表里，否则模型会输出自造病名
        resolved: list[str] = []
        for condition in gate.kept:
            term = vocab.resolve(condition.name)
            if term is None:
                record.free_names.append(condition.name)
                record.deleted_count += 1
                continue
            resolved.append(term.name)
        record.kept_conditions = resolved
        record.empty_after_gate = not resolved
        if gate.empty_after_gate:
            # 一条引用都核不上的结论不可输出，降级为需要追问而不是给一个空结论
            record.status = "gate_empty"
            record.triage = None
            record.department = None
            return record
    else:
        raw_conditions = payload.get("conditions")
        record.kept_conditions = [
            str(item.get("name", ""))
            for item in (raw_conditions if isinstance(raw_conditions, list) else [])
            if isinstance(item, dict)
        ]

    return record


def dump(record: Record) -> str:
    return json.dumps(asdict(record), ensure_ascii=False)
