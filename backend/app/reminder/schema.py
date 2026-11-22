"""提醒域的请求与响应模型，字段照 docs/api.md 第 10、2.13 节。"""

from pydantic import BaseModel, Field


class ReminderItem(BaseModel):
    id: int
    kind: str
    due_at: str
    status: str
    title: str
    body: str | None
    snooze_count: int


class ReminderGroups(BaseModel):
    medication: list[ReminderItem]
    followup: list[ReminderItem]
    recheck: list[ReminderItem]


class ReminderListData(BaseModel):
    groups: ReminderGroups
    pending_count: int


class ReminderRespond(BaseModel):
    action: str
    answers: dict[str, str] | None = None
    note: str | None = Field(default=None, max_length=200)


class FollowupAdvice(BaseModel):
    level: str
    text: str


class SupplementOut(BaseModel):
    watch_for: list[str]
    prepare_idx: list[int]
    next_question: str


class ReminderRespondData(BaseModel):
    status: str
    advice: FollowupAdvice | None = None
    supplement: SupplementOut | None = None
    due_at: str | None = None
