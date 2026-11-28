"""问诊域的请求与响应模型，字段与命名照 docs/api.md 第 2、5 节。"""

from pydantic import BaseModel


class CreateEpisodeRequest(BaseModel):
    complaint: str
    city_code: str | None = None


class AnswerRequest(BaseModel):
    """一条回答原文（issue #23 契约第 3 节）：question_id 为 null 表示结果后主动补充。"""

    question_id: str | None = None
    action: str
    text: str = ""


class EpisodeSummary(BaseModel):
    id: int
    status: str
    created_at: str
    saved_at: str | None
    complaint_excerpt: str
    triage: str | None
    triage_label: str | None
    department_primary: str | None
    degraded: bool


class EpisodeOut(BaseModel):
    id: int
    status: str
    created_at: str
    saved_at: str | None
    expires_at: str
    complaint_text: str
    revision: int = 0


class EpisodeDetail(BaseModel):
    episode: EpisodeOut
    normalized: dict[str, object]
    self_attribution: str | None
    env: dict[str, object] | None
    clarify: dict[str, object] | None
    result: dict[str, object] | None
    gate: dict[str, object] | None
    qa_turns: list[dict[str, object]]
    profile_snapshot: dict[str, object]
    vitals_snapshot: dict[str, object]
    # 结果修订历史（issue #23）：保留最近三版供回看
    result_history: list[dict[str, object]] = []
    disclaimer: str
    # 删空通知文案（N1b）：仅 gate.no_conclusion 时非空，前端不再镜像后端文案
    no_conclusion_notice: str | None = None
    # 归档时是否已建提醒（api.md 5.7）：保存行只在它为 true 时提提醒
    reminder_created: bool = False


class PageData(BaseModel):
    records: list[EpisodeSummary]
    total: int
    page: int
    size: int
