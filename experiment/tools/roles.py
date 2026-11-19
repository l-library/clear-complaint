"""按标题判定文件角色，决定是否进语料。

两个入口（覆盖率统计、分片）必须用同一套判据，否则会出现「统计里被排除、
分片里又出现」的文件。质控指标是医院管理指标，流程图是附件示意，两者都不是
分诊依据。
"""

from __future__ import annotations

# (标题关键词, 角色名)。先匹配先赢，所以质控与流程图排在最前。
RULES: tuple[tuple[str, str], ...] = (
    ("质量控制指标", "质控指标"),
    ("重点任务及服务流程图", "流程图"),
    ("流程图", "流程图"),
    ("分级诊疗", "分级诊疗"),
    ("诊疗方案", "诊疗方案"),
    ("诊疗规范", "诊疗规范"),
    ("防控方案", "防控方案"),
    ("防治指南", "防治指南"),
    ("健康服务规范", "健康服务规范"),
)

SKIP_ROLES = frozenset({"质控指标", "流程图"})


def classify(title: str, slug: str = "") -> tuple[str, bool, str]:
    for needle, role in RULES:
        if needle in title:
            if role in SKIP_ROLES:
                return role, False, "与诊疗分诊无关"
            return role, True, ""
    if "诊疗" in slug:
        return "诊疗规范", True, ""
    return "未分类", False, "需人工确认角色"
