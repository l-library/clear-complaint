from harness import vocab


def test_alias_resolves_to_the_canonical_term() -> None:
    term = vocab.resolve("普通感冒（不构成诊断）")

    assert term is not None
    assert term.name == "上呼吸道感染"


def test_longest_match_wins() -> None:
    """「感冒」不该抢走「流行性感冒」。"""
    term = vocab.resolve("流行性感冒")

    assert term is not None
    assert term.name == "流行性感冒"


def test_unknown_name_does_not_resolve() -> None:
    assert vocab.resolve("某种罕见综合征") is None


def test_known_terms_covers_names_and_aliases() -> None:
    known = vocab.known_terms()

    assert "上呼吸道感染" in known
    assert "感冒" in known
