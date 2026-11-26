"""文案与组装：档位标签、紧迫度、就医准备、追问问题卡、平台请求适配。

模板锁定（constraints.md 约束五）：四段固定、档位三值枚举、科室受控表、
病名受控词表。模型只给 triage/department/conditions，其余全部来自这里。
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from app.agent.departments import contains as department_ok

if TYPE_CHECKING:
    from app.account.models import Profile

TRIAGE_LEVELS = ("emergency", "clinic", "self_observe")

TRIAGE_LABELS = {"emergency": "急诊", "clinic": "门诊", "self_observe": "自我观察"}

URGENCY_NOTES = {
    "emergency": "建议立即或数小时内就医",
    "clinic": "建议数日内就诊，症状加重时提前",
    "self_observe": "症状较轻可先自我观察，一周内复评",
}

# 就医准备按档位套模板；引用段（conditions）带依据，不在模板里
PREP_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "emergency": {
        "bring": ["医保卡与既往检查报告", "正在服用的药物清单"],
        "describe": ["现在最难受的表现和开始时间", "慢性病与过敏史"],
        "go_now": ["立即前往急诊或拨打 120", "不要自行驾车前往"],
    },
    "clinic": {
        "bring": ["医保卡与既往检查报告", "正在服用的药物清单"],
        "describe": ["症状从什么时候开始", "症状的变化过程与伴随表现"],
        "go_now": ["出现呼吸困难、高热不退或意识改变时，立即前往急诊"],
    },
    "self_observe": {
        "bring": [],
        "describe": ["记录症状开始时间与每日变化", "就诊时带上这份记录"],
        "go_now": ["症状加重或超过一周未缓解，去门诊复评"],
    },
}

DISCLAIMER = "清诉不构成诊断，最终判断以医生为准。"

STAGE_TEXTS = {
    "normalize": "正在理解你的描述",
    "clarify": "还需要补充一点信息",
    "retrieve": "正在检索相关资料",
    "draft": "正在形成初步评估",
    "gate": "正在核验结论依据",
    "compose": "正在整理建议",
    "degraded": "平台暂时不可用，已采用保守建议",
}

# v2 起追问卡片由工作流选题、后端赋号转发（api-agentarts 16.3-v2），本地模板退役

EPISODE_RETENTION_DAYS = 30


COVERAGE_NOTE = "资料库暂不覆盖你描述的这类表现，以下仅按紧急程度与就诊科室作参考，不包含病因判断。"
NOT_UNDERSTOOD_NOTICE = "这次没太听懂你的描述。可以换句话再说一遍，比如哪里不舒服、什么时候开始的。"


def coverage_result(
    triage: str,
    department_primary: str,
    department_secondary: str | None,
) -> dict[str, Any]:
    """覆盖范围版（issue #23 三出口之二）：理解了、语料不含。

    档位与科室保留、conditions 整节空；单向阀把无依据的 self_observe 抬到
    clinic，emergency 保留——无引用的判断只许往保守方向行使。
    """
    level = triage if triage in TRIAGE_LEVELS else "clinic"
    if level == "self_observe":
        level = "clinic"
    primary = department_primary if department_ok(department_primary) else "全科医学科"
    secondary = (
        department_secondary
        if department_secondary and department_ok(department_secondary)
        else None
    )
    return {
        "triage": level,
        "triage_label": TRIAGE_LABELS[level],
        "urgency_note": URGENCY_NOTES[level],
        "department_primary": primary,
        "department_secondary": secondary,
        "conditions": [],
        "prep": PREP_TEMPLATES[level],
        "out_of_coverage": True,
    }


def fallback_result() -> dict[str, Any]:
    """兜底模板：有档位有科室，不装作有依据（docs/api.md 13 节）。"""
    return {
        "triage": "clinic",
        "triage_label": TRIAGE_LABELS["clinic"],
        "urgency_note": URGENCY_NOTES["clinic"],
        "department_primary": "全科医学科",
        "department_secondary": None,
        "conditions": [],
        "prep": PREP_TEMPLATES["clinic"],
        "degraded": True,
    }


def compose_result(
    triage: str,
    department_primary: str,
    department_secondary: str | None,
    conditions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """把平台草稿折成公开 Result；档位或科室不合法返回 None（按 4004 兜底）。"""
    if triage not in TRIAGE_LEVELS:
        return None
    if not department_ok(department_primary):
        return None
    if department_secondary is not None and not department_ok(department_secondary):
        department_secondary = None
    if triage == "emergency" and department_primary != "急诊科":
        # 16.3.2：急诊档首推必须是急诊科
        department_primary = "急诊科"
        department_secondary = None
    return {
        "triage": triage,
        "triage_label": TRIAGE_LABELS[triage],
        "urgency_note": URGENCY_NOTES[triage],
        "department_primary": department_primary,
        "department_secondary": department_secondary,
        "conditions": conditions[:5],
        "prep": PREP_TEMPLATES[triage],
        "degraded": False,
    }


def map_profile_snapshot(profile: Profile) -> dict[str, Any]:
    """公开 Profile → 16.3.1 的 profile_snapshot。null/[] 的未知语义按契约编码。

    必填项（birth_date、sex）在问诊入口已用 3001 拦下，age 在这里必有值。
    """
    conditions = profile.conditions if profile.conditions is not None else ["unknown"]
    allergies = profile.allergies if profile.allergies is not None else ["unknown"]
    assert profile.birth_date is not None  # 必填项在问诊入口已用 3001 拦下
    today = date.today()
    age = today.year - profile.birth_date.year
    if (today.month, today.day) < (profile.birth_date.month, profile.birth_date.day):
        age -= 1
    return {
        "age": age,
        # v2 平台只认 male/female/other/unknown（api-agentarts 16.3-v2）；
        # 公开档案保持 undisclosed 原值，这里只做出站适配
        "sex": "unknown" if profile.sex == "undisclosed" else profile.sex,
        "conditions": list(conditions),
        "condition_note": profile.condition_note or "",
        "allergies": list(allergies),
        "allergy_note": profile.allergy_note or "",
    }


def red_flag_result() -> dict[str, Any]:
    """红旗短路的结论：不走模型，科室固定急诊科。"""
    return {
        "triage": "emergency",
        "triage_label": TRIAGE_LABELS["emergency"],
        "urgency_note": URGENCY_NOTES["emergency"],
        "department_primary": "急诊科",
        "department_secondary": None,
        "conditions": [],
        "prep": PREP_TEMPLATES["emergency"],
        "degraded": False,
    }


def excerpt(complaint: str, limit: int = 30) -> str:
    return complaint if len(complaint) <= limit else complaint[: limit - 1] + "…"
