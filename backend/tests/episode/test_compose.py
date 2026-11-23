"""compose 的首轮时间抽取与追问选项。

选项守护对应平台契约：AgentArts 工作流解析不了含阿拉伯数字的时长，
选了即判 insufficient_evidence 走兜底（2026-11 实测）。改动选项前先对
平台实测，再改这里。
"""

import pytest

from app.episode import compose


@pytest.mark.parametrize(
    ("complaint", "expected"),
    [
        # 「X天了」句式：主诉里最常见的病程写法
        ("发热两天了", {"onset_at": None, "duration_text": "两天"}),
        ("流鼻涕三天了，有点乏力", {"onset_at": None, "duration_text": "三天"}),
        # 「持续」句式，含「了」与不含
        ("嗓子疼，持续了三天", {"onset_at": None, "duration_text": "三天"}),
        ("咳嗽持续一周", {"onset_at": None, "duration_text": "一周"}),
        # 起点句式
        ("两天前开始发烧", {"onset_at": "两天前开始", "duration_text": None}),
        ("昨天开始头疼", {"onset_at": "昨天开始", "duration_text": None}),
        ("前天起出现皮疹", {"onset_at": "前天起", "duration_text": None}),
        # 两样都写了：各自提取，互不干扰
        (
            "两天前开始嗓子疼，持续三天了",
            {"onset_at": "两天前开始", "duration_text": "三天"},
        ),
        # 拿不准的不填：三天前吃的是药不是起病，留给追问
        ("三天前吃了退烧药，现在还烧", {"onset_at": None, "duration_text": None}),
        # 无时间信息
        ("我觉得是感冒", {"onset_at": None, "duration_text": None}),
        # 误报守护：非病程词不能命中
        ("白天疼，夜里不疼", {"onset_at": None, "duration_text": None}),
        ("每天早上都咳嗽", {"onset_at": None, "duration_text": None}),
    ],
)
def test_build_initial_times(complaint: str, expected: dict[str, None | str]) -> None:
    assert compose.build_initial_times(complaint, None) == expected


def test_build_initial_times_strips_attribution() -> None:
    # 自我归因段里带时间词时，时间抽取只看摘掉归因后的主诉
    result = compose.build_initial_times("我感冒两天了", "感冒")
    assert result["duration_text"] == "两天"


def test_duration_options_carry_no_digits() -> None:
    # 平台解析不了含阿拉伯数字的时长；选项含数字等于让用户点一个必死答案
    options = compose.QUESTION_TEMPLATES["duration_text"]["options"]
    assert options
    for option in options:
        assert not any(character.isdigit() for character in option), option


@pytest.mark.parametrize(
    ("complaint", "expected"),
    [
        # 温度数字剔除：含「385度」的整句平台检索不到证据，剔除后实测通过
        (
            "发热两天了，最高38.5度，咽痛和乏力",
            ["发热两天了咽痛和乏力"],
        ),
        ("烧到39度", ["烧到39度"]),  # 剔除后为空，退回原文
        ("流鼻涕三天了", ["流涕三天了"]),  # 原有行为不变
    ],
)
def test_build_initial_normalized_strips_degrees(complaint: str, expected: list[str]) -> None:
    assert compose.build_initial_normalized(complaint, None) == expected
