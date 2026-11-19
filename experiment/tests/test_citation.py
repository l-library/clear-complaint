from harness.citation import Condition, verify

POOL = [
    "主要表现为发热、流涕、咳嗽、流泪、畏光和斑丘疹等，少部分可出现肺炎、喉炎等并发症。",
    "起病急，表现为急性发作的呕吐、腹泻，可伴恶心、腹痛、头痛、肌痛等。",
]


def test_verbatim_quote_passes() -> None:
    condition = Condition(
        name="诺如病毒胃肠炎", evidence_idx=[1], quote="急性发作的呕吐、腹泻，可伴恶心"
    )

    result = verify([condition], POOL)

    assert [item.name for item in result.kept] == ["诺如病毒胃肠炎"]
    assert result.deleted == []
    assert not result.empty_after_gate


def test_one_wrong_character_deletes_the_condition() -> None:
    # 同义词不算逐字：把「发烧」当「发热」放宽，逐字核验就不再可证
    condition = Condition(name="麻疹", evidence_idx=[0], quote="主要表现为发烧、流涕、咳嗽")

    result = verify([condition], POOL)

    assert result.kept == []
    assert result.deleted_count == 1
    assert result.empty_after_gate


def test_short_quote_cannot_sneak_through() -> None:
    """短于 8 字的匹配会让「发热」这种词轻松过关，闸门形同虚设。"""
    condition = Condition(name="麻疹", evidence_idx=[0], quote="发热")

    assert verify([condition], POOL).deleted_count == 1


def test_quote_must_come_from_the_cited_index() -> None:
    """借用别处的原文来担保同样算核不上。"""
    condition = Condition(name="麻疹", evidence_idx=[0], quote="急性发作的呕吐、腹泻，可伴恶心")

    assert verify([condition], POOL).deleted_count == 1


def test_out_of_range_index_is_deleted_not_crashed() -> None:
    condition = Condition(name="麻疹", evidence_idx=[9], quote="主要表现为发热、流涕、咳嗽")

    assert verify([condition], POOL).deleted_count == 1


def test_condition_without_any_index_is_deleted() -> None:
    assert verify([Condition(name="麻疹", evidence_idx=[])], POOL).deleted_count == 1


def test_whitespace_and_punctuation_differences_still_pass() -> None:
    """全半角与空白的差异不该让一条真实引用被删，错字才该被删。"""
    condition = Condition(
        name="诺如病毒胃肠炎", evidence_idx=[1], quote="起病急, 表现为急性发作的呕吐"
    )

    assert verify([condition], POOL).deleted_count == 0
