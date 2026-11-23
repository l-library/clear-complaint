"""文案与组装：档位标签、紧迫度、就医准备、追问问题卡、平台请求适配。

模板锁定（constraints.md 约束五）：四段固定、档位三值枚举、科室受控表、
病名受控词表。模型只给 triage/department/conditions，其余全部来自这里。
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Any

from app.agent.departments import contains as department_ok
from app.agent.normalize import normalize

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

# 公开字段名 ↔ 平台字段名（docs/api-agentarts.md 16.3.1 的适配表）
FIELD_TO_PLATFORM = {
    "onset_at": "onset",
    "duration_text": "duration",
    "site": "location",
    "nature": "character",
    "associated": "associated_symptoms",
    "medications_text": "medication",
}
FIELD_FROM_PLATFORM = {value: key for key, value in FIELD_TO_PLATFORM.items()}

# 追问问题卡（constraints.md 约束二：按字段问，不做泛化提问）
QUESTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "onset_at": {"text": "症状是从什么时候开始的？", "options": [], "allow_free_text": True},
    "duration_text": {
        "text": "这种情况持续了多久？",
        # 平台工作流解析不了含阿拉伯数字的时长（实测 3天、1 周、1–3 天 全部
        # insufficient_evidence，选了即兜底）。选项只用平台认可的中文数量词；
        # 改动前先对平台实测，tests/episode/test_compose.py 有守护。
        "options": ["半天", "一两天", "两三天", "一周", "一周以上"],
        "allow_free_text": True,
    },
    "site": {"text": "不舒服的部位在哪里？", "options": [], "allow_free_text": True},
    "nature": {
        "text": "是什么样的感觉（比如胀痛、刺痛、清水样）？",
        "options": [],
        "allow_free_text": True,
    },
    "associated": {"text": "还有别的不舒服吗？", "options": [], "allow_free_text": True},
    "medications_text": {
        "text": "这次生病后用过什么药吗？",
        "options": ["没用药"],
        "allow_free_text": True,
    },
}

# 明确未知的编码：平台按 16.3.4 的口径不再把该字段当未答问题
UNKNOWN_VALUE = "unknown"

CLARIFY_ROUND_LIMIT = 5
EPISODE_RETENTION_DAYS = 30


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


def compose_questions(fields: list[str]) -> list[dict[str, Any]]:
    questions = []
    for field in fields:
        template = QUESTION_TEMPLATES[field]
        questions.append(
            {
                "field": field,
                "text": template["text"],
                "options": list(template["options"]),
                "allow_free_text": template["allow_free_text"],
            }
        )
    return questions


def build_platform_request(
    *,
    episode_id: int,
    request_id: str,
    complaint_text: str,
    normalized_public: dict[str, Any],
    self_attribution: str | None,
    profile_snapshot: dict[str, Any],
    clarify_state: dict[str, Any],
    red_flag_ids: list[str],
) -> dict[str, Any]:
    """组装 16.3.1 的业务请求。normalized 字段名在这里完成公开→平台映射。"""
    platform_normalized: dict[str, Any] = {
        "symptom": " ".join(normalized_public.get("symptom") or []),
        "onset": normalized_public.get("onset_at"),
        "duration": normalized_public.get("duration_text"),
        "location": normalized_public.get("site"),
        "character": normalized_public.get("nature"),
        "associated_symptoms": normalized_public.get("associated"),
        "medication": normalized_public.get("medications_text"),
    }
    return {
        "schema_version": "clear-complaint.triage.request.v1",
        "episode_id": str(episode_id),
        "request_id": request_id,
        "episode_status": "generating",
        "complaint_text": complaint_text,
        "normalized": platform_normalized,
        "self_attribution": [self_attribution] if self_attribution else [],
        "profile_snapshot": profile_snapshot,
        "vitals_snapshot": {},
        "env": {},
        "clarification": {
            "round": int(clarify_state.get("round", 0)),
            "round_limit": CLARIFY_ROUND_LIMIT,
            "skipped": bool(clarify_state.get("skipped", False)),
        },
        "red_flags": {"checked": True, "version": 1, "matched_rule_ids": red_flag_ids},
    }


# 首轮时间抽取。主诉里已写明病程（「发烧两天了」「持续三天」）或起点（「两天前
# 开始」「昨天开始」）时填进首轮 normalized，平台就不会把用户答过的时间再问
# 一遍。只认高置信句式：拿不准的留给追问，宁可多问一句也不错填一个字段，
# 错的时间会顺着平台请求一路走到底。
_NUMERAL = r"(?:半|[一二两三四五六七八九十]{1,2})"
_UNIT = r"(?:天|日|周)"
_DURATION_ONGOING_RE = re.compile(rf"({_NUMERAL})({_UNIT})了")
_DURATION_SUSTAIN_RE = re.compile(rf"持续了?({_NUMERAL})({_UNIT})")
_ONSET_RE = re.compile(rf"(?:{_NUMERAL}(?:天|日)前|(?:昨|前)天)(?:开始|起|出现)")


def build_initial_times(complaint: str, attribution: str | None) -> dict[str, str | None]:
    """从主诉提取高置信的起病时间与病程，供 create_episode 填入首轮 normalized。"""
    text = complaint if attribution is None else _strip_attribution(complaint, attribution)
    folded = normalize(text)
    duration: str | None = None
    for pattern in (_DURATION_SUSTAIN_RE, _DURATION_ONGOING_RE):
        match = pattern.search(folded)
        if match:
            duration = match.group(1) + match.group(2)
            break
    onset_match = _ONSET_RE.search(folded)
    return {
        "onset_at": onset_match.group(0) if onset_match else None,
        "duration_text": duration,
    }


# 平台的 symptom 检索吃不下温度数字：实测「发热最高385度咽痛和乏力」整句
# NO_RETRIEVAL_EVIDENCE，剔除温度后同句两次 draft_ready。高热的定档走红旗
# 规则，查的是原文，不依赖这里的 symptom。
_DEGREE_RE = re.compile(r"(?:最高|高达|超过|烧到|到了|大约|大概|约)?\d+(?:[.．]?\d+)?(?:度|℃)")


def build_initial_normalized(complaint: str, attribution: str | None) -> list[str]:
    """初始归一化：摘掉自我归因后折整句为 symptom（字段级抽取不在本版）。"""
    text = complaint if attribution is None else _strip_attribution(complaint, attribution)
    folded = _DEGREE_RE.sub("", normalize(text))
    return [folded] if folded else [complaint]


def _strip_attribution(complaint: str, attribution: str) -> str:
    remainder = complaint.replace(attribution, "")
    return remainder.strip(" ，,。.；;") or complaint


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
        "sex": profile.sex,
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
