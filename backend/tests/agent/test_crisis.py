"""危机分流机制：合成词面走查全部行为；线上词面评审前为空。"""

from app.agent import crisis
from app.agent.normalize import normalize


def _synthetic() -> tuple[crisis.CrisisHit, ...]:
    return (
        crisis.CrisisHit(
            rule_id="CR01", name="自伤意图", triggers=("不想活", "轻生", "结束自己的生命")
        ),
        crisis.CrisisHit(rule_id="CR02", name="自伤表述", triggers=("伤害自己",)),
    )


def test_live_rules_empty_until_review() -> None:
    # 评审前线上命中恒为零：机制生效、词面待评审（issue #23 第 6 节）
    assert crisis.rules() == ()
    assert crisis.detect("我不想活了，想结束自己的生命") == []


def test_detect_matches_and_normalizes() -> None:
    ruleset = _synthetic()
    hits = crisis.detect("最近压力大，不想活了的念头一直在", ruleset=ruleset)
    assert [hit.rule_id for hit in hits] == ["CR01"]

    both = crisis.detect("既想轻生又想伤害自己", ruleset=ruleset)
    assert [hit.rule_id for hit in both] == ["CR01", "CR02"]

    # 归一化照常生效：normalize 是精选错拼对照表（「心huang」→「心慌」），
    # rules() 装表时归一 triggers，合成词面在构造时对齐同一处理
    pinyin = crisis.CrisisHit(rule_id="CR03", name="错拼走查", triggers=(normalize("心慌"),))
    assert crisis.detect("最近总是有点心huang", ruleset=(pinyin,))
    clean = crisis.detect("我昨天心情不错", ruleset=ruleset)
    assert clean == []


def test_negation_is_deliberately_not_filtered() -> None:
    # 有意的取舍：否定语境不过滤。漏检真求助的代价远高于多复核一条，
    # 「没有想过轻生」命中后走人工复核，不做自动分诊
    ruleset = _synthetic()
    assert crisis.detect("以前想过轻生，现在没有这个念头了", ruleset=ruleset)


def test_disposition_payload_shape() -> None:
    hits = crisis.detect("不想活", ruleset=_synthetic())
    payload = crisis.disposition(hits)
    assert payload["kind"] == "crisis"
    assert payload["rule_ids"] == ["CR01"]
    assert payload["version"] == crisis.version()
    copy = payload["copy"]
    assert isinstance(copy, list)
    assert any("12356" in line for line in copy)
    assert any("120" in line for line in copy)
    # 固定文案不出现档位、科室等分诊词汇：危机不是分诊结论
    joined = "".join(line for line in copy if isinstance(line, str))
    assert "急诊科" not in joined and "门诊" not in joined and "自我观察" not in joined
