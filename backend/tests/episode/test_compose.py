"""compose 的 v2 产物：覆盖范围版结果、单向阀与删空不出档的声明文案。

v1 的预提取与追问模板已随 request.v2 退役（理解归工作流），
这里只覆盖新增的出口文案与受控取值。
"""

from app.episode import compose


def test_coverage_result_valve_lifts_self_observe() -> None:
    # 单向阀：无引用的 self_observe 必须抬到 clinic，emergency 保留
    lifted = compose.coverage_result("self_observe", "皮肤科", None)
    assert lifted["triage"] == "clinic"
    assert lifted["triage_label"] == "门诊"
    assert lifted["out_of_coverage"] is True
    assert lifted["conditions"] == []

    kept = compose.coverage_result("emergency", "急诊科", None)
    assert kept["triage"] == "emergency"
    assert kept["out_of_coverage"] is True


def test_coverage_result_falls_back_to_safe_defaults() -> None:
    # 未知档位按保守处理；科室不在受控表回落全科
    result = compose.coverage_result("vibes", "银河系诊所", "不存在科")
    assert result["triage"] == "clinic"
    assert result["department_primary"] == "全科医学科"
    assert result["department_secondary"] is None

    good = compose.coverage_result("clinic", "呼吸内科", "感染科")
    assert good["department_primary"] == "呼吸内科"
    assert good["department_secondary"] == "感染科"


def test_coverage_note_is_a_boundary_statement() -> None:
    # 覆盖范围声明必须是边界声明，不得伪装成结论或兜底话术
    assert "不覆盖" in compose.COVERAGE_NOTE
    assert "不包含病因判断" in compose.COVERAGE_NOTE
    assert "兜底" not in compose.COVERAGE_NOTE


def test_not_understood_notice_is_conversational() -> None:
    # 没听懂版是对话式追问，不吐分诊模板
    assert "没太听懂" in compose.NOT_UNDERSTOOD_NOTICE
    assert "门诊" not in compose.NOT_UNDERSTOOD_NOTICE
    assert "急诊" not in compose.NOT_UNDERSTOOD_NOTICE


def test_no_conclusion_notice_is_a_boundary_statement() -> None:
    # 删空不出档（约束四）：声明给不出结论，不出现档位或科室字样，只给下一步
    assert "不提供分诊档位与就诊科室" in compose.NO_CONCLUSION_NOTICE
    for label in compose.TRIAGE_LABELS.values():
        assert label not in compose.NO_CONCLUSION_NOTICE
    assert "全科医学科" not in compose.NO_CONCLUSION_NOTICE
    assert "再发起一次" in compose.NO_CONCLUSION_NOTICE
