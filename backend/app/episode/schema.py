"""问诊域的请求与响应模型，字段与命名照 docs/api.md 第 2、5 节。"""

from pydantic import BaseModel, Field


class CreateEpisodeRequest(BaseModel):
    complaint: str
    city_code: str | None = None


class ClarifyAnswer(BaseModel):
    field: str
    value: str = ""
    is_unknown: bool = False


class ClarifyRequest(BaseModel):
    answers: list[ClarifyAnswer] = Field(min_length=1, max_length=5)


class SaveEpisodeRequest(BaseModel):
    save: bool = True
    reminder: bool = True
    recheck_date: str | None = None


class ReminderOut(BaseModel):
    id: int
    kind: str
    due_at: str


class SaveEpisodeData(BaseModel):
    saved_at: str | None
    reminder: ReminderOut | None


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
    disclaimer: str


class PageData(BaseModel):
    records: list[EpisodeSummary]
    total: int
    page: int
    size: int
