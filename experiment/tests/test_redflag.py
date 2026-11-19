from harness import redflag


def test_colloquial_chest_pain_triggers_the_rule() -> None:
    """用患者会说的话也要能命中——触发词表里既有原文短语也有口语说法。"""
    hits = redflag.detect("胸口压得慌，出冷汗")

    assert {hit.rule_id for hit in hits} >= {"RF12"}


def test_pinyin_and_typos_do_not_evade_the_rule() -> None:
    """V5 变体：归一化不做成模型动作，正是为了红旗不被错别字绕过。"""
    hits = redflag.detect("喘不上气，嘴唇发紫")

    assert {hit.rule_id for hit in hits} >= {"RF03", "RF04"}


def test_prolonged_fever_triggers() -> None:
    assert {hit.rule_id for hit in redflag.detect("已经烧了三天了")} >= {"RF06"}


def test_plain_complaint_triggers_nothing() -> None:
    assert redflag.detect("我最近常常流鼻涕") == []


def test_red_flag_beats_clarification() -> None:
    """红旗短路优先于澄清追问：安全优先，缺字段也要先给急诊档。"""
    assert redflag.triage_level("胸痛超过20分钟不缓解") == "emergency"
    assert redflag.triage_level("流鼻涕") == "undetermined"


def test_every_rule_keeps_its_source() -> None:
    for rule in redflag.rules():
        assert rule.chunk_id
        assert rule.quote


def test_colloquial_chest_pain_phrasings_all_hit() -> None:
    """患者不会说「胸痛」：胸口疼、心口疼、胸口痛都要命中同一条规则。"""
    for text in ("胸口疼，出汗二十分钟了", "心口疼得厉害", "胸口痛，闷得慌"):
        assert "RF12" in {hit.rule_id for hit in redflag.detect(text)}, text
