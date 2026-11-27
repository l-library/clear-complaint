"""日报域的请求与响应模型，字段照 docs/api.md 第 16 节与 docs/api-agentarts.md 16.8.7。"""

from pydantic import BaseModel, ConfigDict


class DailyGenerateRequest(BaseModel):
    """生成请求体只有日期一项：手表指标与档案都由后端自己拼（16.8.8 第 1 条）。

    `extra="forbid"` 是关键：多传 `watch_data`、`health_archive` 之类的键必须报错，
    而不是被静默忽略后让人以为"后端用了前端提交的指标"。
    """

    model_config = ConfigDict(extra="forbid")

    report_date: str | None = None


class DailyReportOut(BaseModel):
    """一份当日报告的对外形状；`summary` 为 null 是 review_required 的合法形态。"""

    report_date: str
    status: str
    degraded: bool
    data_source: str
    workflow_version: str
    summary: dict[str, object] | None
    data_quality: dict[str, object] | None
    used_record_ids: list[str]
    created_at: str
    updated_at: str
