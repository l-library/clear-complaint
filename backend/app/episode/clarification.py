"""Deterministic field handling shared by the API adapter and workflow export."""

import re
import unicodedata
from collections.abc import Mapping

FIELDS = {
    "onset": "onset_at",
    "duration": "duration_text",
    "location": "site",
    "character": "nature",
    "associated_symptoms": "associated",
    "medication": "medications_text",
}
UNKNOWN = {"unknown", "不知道", "不清楚", "不确定", "未知", "未提供", "不详", "跳过"}


def is_unknown(value: str) -> bool:
    return value.strip().lower() in UNKNOWN


def canonical_duration(value: str | None) -> str | None:
    """Keep ranges and qualifiers; never turn a range into a single duration."""
    if value is None:
        return None
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
    quantity = r"[\d零一二三四五六七八九十百两半点.]+"
    unit = r"(?:分钟|小时|天|日|周|星期|个月|月|年)"
    if not re.fullmatch(
        rf"(?:持续|已经|已)?(?:不到|不足|约|大约|近|超过)?{quantity}"
        rf"(?:{unit})?(?:[–—~～至到-]{quantity})?{unit}(?:左右|以上|以下|多)?",
        text,
    ):
        return value.strip()
    text = re.sub(r"[–—~～-]", "至", text)

    def number(match: re.Match[str]) -> str:
        integer = int(match.group())
        if integer >= 100:
            return match.group()
        digits = "零一二三四五六七八九"
        if integer < 10:
            return digits[integer]
        tens, units = divmod(integer, 10)
        return (digits[tens] if tens > 1 else "") + "十" + (digits[units] if units else "")

    return re.sub(r"(?<![\d.])\d+(?![\d.])", number, text)


def pending_fields(result: Mapping[str, object], normalized: Mapping[str, object]) -> list[str]:
    request = result.get("clarification_request")
    details = request if isinstance(request, dict) else {}
    missing = details.get("missing_fields", result.get("missing_fields", []))
    requested = details.get("question_fields", [])
    unknown = result.get("unknown_fields", [])
    excluded = (
        {item for item in unknown if isinstance(item, str)} if isinstance(unknown, list) else set()
    )
    candidates = (requested if isinstance(requested, list) else []) + (
        missing if isinstance(missing, list) else []
    )
    fields: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str) or candidate not in FIELDS or candidate in excluded:
            continue
        value = normalized.get(FIELDS[candidate])
        if isinstance(value, str) and value.strip():
            # Both known and explicitly unknown answers have already been answered.
            continue
        if candidate not in fields:
            fields.append(candidate)
    return fields
