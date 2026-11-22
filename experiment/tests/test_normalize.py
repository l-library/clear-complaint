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


def test_pinyin_folds_back_to_hanzi() -> None:
    """V5 变体的整条约束就是「归一化能折回去」，折不了这条约束等于没测。"""
    folded = normalize("shou上jiao上起了小水pao，嘴chun发紫")

    assert "水疱" in folded
    assert "手上" in folded
    assert "嘴唇" in folded
    assert not any(token.isascii() for token in folded)


def test_longer_pinyin_tokens_win() -> None:
    """按长度从长到短替换：否则 ke 会把 keng 吃成「咳ng」。"""
    assert "坑" in normalize("按下去一个keng")
    assert normalize("睡gou了") == normalize("睡够了")
    assert normalize("被gou咬了") == normalize("被狗咬了")


def test_no_case_leaves_pinyin_behind() -> None:
    """拿病例集当回归：V5 归一化之后不该再有拉丁字母残留。"""
    import json
    import re
    from pathlib import Path

    cases = Path(__file__).resolve().parent.parent / "cases"
    for name in ("drafts.jsonl", "pilot.jsonl"):
        for line in (cases / name).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            folded = normalize(row["variants"]["V5"])
            assert not re.findall(r"[a-z]{2,}", folded), row["case_id"]


def test_chronic_disease_colloquialisms_fold_to_clinical_forms() -> None:
    """族实验补充的口语映射：慢性病与体征的叫法折成指南用语。"""
    assert "慢性阻塞性肺疾病" in normalize("慢阻肺十年，长期吸入药物")
    assert normalize("腿有点肿") == "下肢水肿"
    assert normalize("两条腿肿了一个月") == "两条下肢水肿了一个月"
    assert normalize("人也容易累") == "人也疲乏"
    assert normalize("身上起了些小水泡") == "身上起了些小水疱"


def test_new_mappings_do_not_arm_any_red_flag() -> None:
    """映射把「下肢水肿」「疲乏」这类临床词引进归一文本，红旗表里不得有词因此误触。"""
    from harness import redflag

    texts = [
        "最近两周两条腿有点肿，按下去一个浅坑，人也容易累",
        "慢阻肺十年，这几天咳嗽多了些，痰也多了",
        "两天前身上起了些小水泡，有点痒，还有点低热",
    ]
    for text in texts:
        assert redflag.detect(text) == [], text
