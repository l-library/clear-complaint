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


def test_negated_symptom_does_not_fire() -> None:
    """「没有胸痛」不是胸痛。子串匹配不认语境，规则要安全就得先看懂否定。"""
    assert redflag.detect("没有胸痛，也没晕，心慌两小时") == []
    assert redflag.detect("否认药物过敏，流鼻涕三天") == []


def test_hypothetical_does_not_fire() -> None:
    """「会不会脱水」是担心，不是征象。"""
    assert redflag.detect("我很担心，腹泻三天，会不会脱水") == []


def test_negation_after_the_trigger_still_fires() -> None:
    """否定词在触发词之后时，毛病是真的，照常命中。"""
    assert {hit.rule_id for hit in redflag.detect("胸口疼，没有缓解，出汗")} >= {"RF12"}


def test_one_unnegated_mention_is_enough() -> None:
    """同一句里既有否定也有肯定时，肯定那处要算命中。"""
    hits = redflag.detect("一开始没有胸痛，今天开始胸口疼，出汗")
    assert {hit.rule_id for hit in hits} >= {"RF12"}
