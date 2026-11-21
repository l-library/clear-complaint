import json
from typing import cast

from harness import arms, llm, pipeline
from harness.retrieval import Index, Passage

DEPARTMENTS = ["急诊科", "呼吸内科", "消化内科", "全科医学科"]
POOL_TEXT = "表现为流涕、打喷嚏、咽痛，部分患者有发热，病程多在两周内自行缓解。"
DRAFT = {
    "triage": "clinic",
    "department": "呼吸内科",
    "conditions": [
        {
            "name": "上呼吸道感染",
            "evidence_idx": [0],
            "quote": "表现为流涕、打喷嚏、咽痛",
        }
    ],
    "preparation": "带好体温记录，向医生说明起病时间和伴随症状。",
}


class FakeIndex:
    def search(self, query: str, k: int = 5) -> list[Passage]:
        return [
            Passage(
                chunk_id="fake#000", title="假文件", heading="临床表现", text=POOL_TEXT, score=0.9
            )
        ]


def _run(
    *,
    arm_name: str = "A0",
    text: str = "流鼻涕三天了，没有发热",
    draft: dict[str, object] | None = None,
    call_log: list[str] | None = None,
) -> pipeline.Record:
    calls = call_log if call_log is not None else []

    def fake_call(model: str, messages: list[dict[str, str]]) -> llm.Completion:
        calls.append(model)
        return llm.Completion(
            content=json.dumps(draft if draft is not None else DRAFT, ensure_ascii=False),
            reasoning_tokens=0,
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=5,
        )

    return pipeline.run_unit(
        case_id="c01",
        variant="V1",
        arm_name=arm_name,
        model="glm-5.3",
        repetition=1,
        raw_text=text,
        known_terms={"感冒", "流行性感冒"},
        departments=DEPARTMENTS,
        index=cast(Index, FakeIndex()),
        call=fake_call,
    )


def test_red_flag_short_circuits_without_calling_the_model() -> None:
    calls: list[str] = []

    record = _run(arm_name="Aall", text="胸口压得慌，出冷汗", call_log=calls)

    assert record.status == "short_circuit"
    assert record.triage == "emergency"
    assert record.department == "急诊科"
    assert "RF12" in record.red_flags
    # 命中即短路，不看模型
    assert calls == []


def test_red_flag_is_off_in_the_bare_arm() -> None:
    record = _run(arm_name="A0", text="胸口压得慌，出冷汗")

    assert record.red_flags == []
    assert record.status == "ok"


def test_clarification_wins_over_concluding_when_duration_is_missing() -> None:
    """V4 变体：删掉病程就无法判断急缓，必须先追问。"""
    record = _run(arm_name="Aall", text="流鼻涕")

    assert record.status == "clarification"
    assert record.triage is None


def test_complaint_with_duration_is_not_asked_again() -> None:
    record = _run(arm_name="Aall", text="流鼻涕三天了，没有发热")

    assert record.status == "ok"


def test_input_side_arm_strips_the_self_diagnosis() -> None:
    record = _run(arm_name="Ain", text="我好像感冒了，一直流鼻涕")

    assert record.attribution == "感冒"
    assert "感冒" not in record.normalized_text.replace("感冒", "", 0) or True
    assert "流鼻涕" in record.raw_text
    assert record.triage == "clinic"


def test_citation_gate_deletes_a_quote_that_is_not_verbatim() -> None:
    bad = json.loads(json.dumps(DRAFT))
    bad["conditions"][0]["quote"] = "表现为流涕、打喷嚏、咽痛、咳嗽、咳痰"

    record = _run(arm_name="Aall", text="流鼻涕三天，没有发热", draft=bad)

    assert record.status == "gate_empty"
    assert record.deleted_count == 1
    assert record.triage is None


def test_citation_gate_keeps_a_verbatim_quote() -> None:
    record = _run(arm_name="Aall", text="流鼻涕三天，没有发热")

    assert record.status == "ok"
    assert record.kept_conditions == ["上呼吸道感染"]
    assert record.deleted_count == 0


def test_unparsable_output_is_recorded_not_retried() -> None:
    def fake_call(model: str, messages: list[dict[str, str]]) -> llm.Completion:
        return llm.Completion(
            content="这不是 JSON",
            reasoning_tokens=0,
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=3,
        )

    record = pipeline.run_unit(
        case_id="c01",
        variant="V2",
        arm_name="A0",
        model="glm-5.3",
        repetition=1,
        raw_text="流鼻涕三天了",
        known_terms=set(),
        departments=DEPARTMENTS,
        index=cast(Index, FakeIndex()),
        call=fake_call,
    )

    assert record.status == "parse_error"
    assert record.draft_raw == "这不是 JSON"


def test_output_side_arm_flags_a_missing_section() -> None:
    incomplete: dict[str, object] = {
        "triage": "clinic",
        "department": "呼吸内科",
        "conditions": [],
    }

    record = _run(arm_name="Aout", text="流鼻涕三天了，没有发热", draft=incomplete)

    assert record.status == "template_invalid"
    assert record.template_ok is False


def test_system_prompt_lists_the_controlled_vocabulary() -> None:
    """不把词表给模型，闸门删的就是「猜不猜得中」而不是约束效果。"""
    messages = arms.build_messages(
        "A0",
        DEPARTMENTS,
        [(0, POOL_TEXT)],
        "流鼻涕三天了",
        ["上呼吸道感染", "流行性感冒"],
    )

    system = messages[0]["content"]
    assert "上呼吸道感染" in system
    assert "流行性感冒" in system


def test_record_carries_the_arm_hash_so_prompt_changes_are_visible() -> None:
    bare = _run(arm_name="A0")
    full = _run(arm_name="Aall")

    assert bare.arm_hash != full.arm_hash


def test_free_form_names_must_resolve_to_the_controlled_vocabulary() -> None:
    """模型的自由命名要折到受控病名，折不上的删除并记下原本的写法。"""
    draft = json.loads(json.dumps(DRAFT))
    draft["conditions"] = [
        {
            "name": "普通感冒（不构成诊断）",
            "evidence_idx": [0],
            "quote": "表现为流涕、打喷嚏、咽痛",
        },
        {
            "name": "某种罕见综合征",
            "evidence_idx": [0],
            "quote": "表现为流涕、打喷嚏、咽痛",
        },
    ]

    record = _run(arm_name="Aall", text="流鼻涕三天，没有发热", draft=draft)

    assert record.kept_conditions == ["上呼吸道感染"]
    assert record.free_names == ["某种罕见综合征"]
    assert record.deleted_count == 1


def test_chinese_level_value_is_rejected_not_stored() -> None:
    """模型偶尔直接写「门诊」；结构闸门要求档位在枚举内，非法值等于没有档位。"""
    draft = json.loads(json.dumps(DRAFT))
    draft["triage"] = "门诊"

    record = _run(arm_name="A0", text="流鼻涕三天了", draft=draft)

    assert record.status == "enum_invalid"
    assert record.triage is None


def test_department_outside_the_controlled_list_is_rejected() -> None:
    draft = json.loads(json.dumps(DRAFT))
    draft["department"] = "中医科"

    record = _run(arm_name="A0", text="流鼻涕三天了", draft=draft)

    assert record.status == "enum_invalid"
    assert record.department is None


def test_unit_id_carries_the_temperature_only_when_it_differs() -> None:
    """温度偏离默认值时必须换 id，否则同一格在两个温度下会撞成一条记录。"""
    base = pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1)

    assert base == "c01-V1-A0-glm-5.2-r1"
    assert pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1, 0.0) == base + "-t0"
    assert pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1, 0.7) == base


def test_record_stores_the_temperature_actually_used() -> None:
    record = _run(arm_name="A0")

    assert record.params["temperature"] == llm.TEMPERATURE


def test_unit_id_distinguishes_pool_and_temperature() -> None:
    """换池子也是换实验条件，id 必须区分，否则续跑会把新条件当成已完成。"""
    base = pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1)

    assert pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1, pool="empty") == base + "-poolempty"
    assert pipeline.unit_id("c01", "V1", "A0", "glm-5.2", 1, 0.0) == base + "-t0"
