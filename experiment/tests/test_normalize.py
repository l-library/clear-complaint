from harness.normalize import normalize, split_attribution

VOCAB = {"感冒", "流行性感冒", "急性胃肠炎", "胃肠炎", "流感"}


def test_normalize_folds_typos_and_pinyin() -> None:
    # V5 变体：口语 + 拼音 + 错别字混写
    assert "头痛" in normalize("脑壳tong，一直liu鼻涕")
    assert "流涕" in normalize("脑壳tong，一直liu鼻涕")


def test_normalize_folds_full_width_and_whitespace() -> None:
    assert normalize("发 热 ３ 天") == normalize("发热3天")


def test_normalize_maps_colloquial_phrases() -> None:
    folded = normalize("胸口压得慌，还出冷汗")

    assert "胸部压榨性疼痛" in folded
    assert "冷汗" in folded


def test_normalize_is_stable() -> None:
    text = "拉肚子一天，人有点晕"

    assert normalize(text) == normalize(text)
    assert normalize(normalize(text)) == normalize(text)


def test_split_attribution_removes_the_self_diagnosis() -> None:
    remainder, attribution = split_attribution("我好像感冒了，一直流鼻涕", VOCAB)

    assert attribution == "感冒"
    # 归因那段从主诉里摘掉，剩下的才是症状
    assert "感冒" not in remainder
    assert "流鼻涕" in remainder


def test_split_attribution_keeps_plain_complaints_intact() -> None:
    text = "我觉得很冷，一直发抖"

    remainder, attribution = split_attribution(text, VOCAB)

    assert attribution is None
    assert remainder == text
