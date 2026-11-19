import json
from pathlib import Path
from typing import TypedDict, cast

CORPUS = Path(__file__).resolve().parent.parent / "corpus"


class RedFlag(TypedDict):
    rule_id: str
    name: str
    level: str
    triggers: list[str]
    quote: str
    chunk_id: str


class Term(TypedDict):
    name: str
    aliases: list[str]
    domain: str
    department: str
    chunk_id: str


class Department(TypedDict):
    name: str
    note: str


def _json(name: str) -> dict[str, object]:
    return dict(json.loads((CORPUS / name).read_text(encoding="utf-8")))


def _rules() -> list[RedFlag]:
    return cast("list[RedFlag]", _json("red_flags.json")["rules"])


def _terms() -> list[Term]:
    return cast("list[Term]", _json("vocab.json")["terms"])


def _departments() -> list[Department]:
    return cast("list[Department]", _json("departments.json")["departments"])


def _chunks() -> dict[str, str]:
    lines = (CORPUS / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    return {row["chunk_id"]: row["text"] for row in map(json.loads, filter(None, lines))}


def test_every_red_flag_quote_is_verbatim_from_its_chunk() -> None:
    """红旗清单的引文必须是片段的逐字子串。

    这条是「红旗规则绝不咨询模型」的地基：规则要么指向一段真实原文，要么不该存在。
    """
    chunks = _chunks()
    rules = _rules()

    assert rules
    for rule in rules:
        chunk_id = rule["chunk_id"]
        assert chunk_id in chunks, rule["rule_id"]
        assert rule["quote"] in chunks[chunk_id], rule["rule_id"]


def test_red_flags_are_all_emergency_and_have_triggers() -> None:
    rules = _rules()

    for rule in rules:
        assert rule["level"] == "emergency"
        assert rule["triggers"], rule["rule_id"]
        # 口语说法要能命中：至少一条 trigger 不是四字以上的书面短语
        assert any(len(trigger) <= 5 for trigger in rule["triggers"]), rule["rule_id"]


def test_vocab_is_within_cap_and_attested() -> None:
    chunks = _chunks()
    terms = _terms()

    assert len(terms) <= cast(int, _json("vocab.json")["max"]) == 80
    for term in terms:
        assert term["name"] in chunks[term["chunk_id"]], term["name"]


def test_vocab_departments_come_from_the_controlled_list() -> None:
    departments = {row["name"] for row in _departments()}
    terms = _terms()

    assert "急诊科" in departments
    assert "全科医学科" in departments
    for term in terms:
        assert term["department"] in departments, term["name"]


def test_vocab_domains_match_the_locked_nine() -> None:
    domains = {term["domain"] for term in _terms()}

    assert domains == {
        "呼吸道症状",
        "发热待查",
        "腹泻呕吐",
        "皮疹",
        "胸痛心悸",
        "头晕与意识改变",
        "乏力与水肿",
        "伤口与动物致伤",
        "慢病随访",
    }
