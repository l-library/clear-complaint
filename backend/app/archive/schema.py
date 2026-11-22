"""档案域的请求与响应模型，字段照 docs/api.md 第 2.4–2.6、7、8 节。"""

from pydantic import BaseModel, Field


class VitalOut(BaseModel):
    id: int
    kind: str
    measured_at: str
    height_cm: float | None
    weight_kg: float | None
    systolic: int | None
    diastolic: int | None
    pulse: int | None
    created_at: str


class VitalRequest(BaseModel):
    kind: str
    measured_at: str
    height_cm: float | None = None
    weight_kg: float | None = None
    systolic: int | None = None
    diastolic: int | None = None
    pulse: int | None = None


class VitalUpdate(BaseModel):
    measured_at: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    systolic: int | None = None
    diastolic: int | None = None
    pulse: int | None = None


class VitalPage(BaseModel):
    records: list[VitalOut]
    total: int
    page: int
    size: int


class MedicationOut(BaseModel):
    id: int
    name: str
    dosage_text: str | None
    frequency_text: str | None
    kind: str
    started_on: str
    ended_on: str | None
    status: str
    created_at: str


class MedicationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    dosage_text: str | None = Field(default=None, max_length=40)
    frequency_text: str | None = Field(default=None, max_length=40)
    kind: str
    started_on: str
    ended_on: str | None = None


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    dosage_text: str | None = Field(default=None, max_length=40)
    frequency_text: str | None = Field(default=None, max_length=40)
    ended_on: str | None = None
    status: str | None = None


class MedicationList(BaseModel):
    records: list[MedicationOut]


class MedicationPlanOut(BaseModel):
    id: int
    medication_id: int
    times: list[str]
    started_on: str
    ended_on: str | None
    status: str
    note: str | None
    created_at: str


class MedicationPlanRequest(BaseModel):
    medication_id: int
    times: list[str] = Field(min_length=1, max_length=4)
    started_on: str
    ended_on: str | None = None
    note: str | None = Field(default=None, max_length=200)


class MedicationPlanUpdate(BaseModel):
    times: list[str] | None = Field(default=None, min_length=1, max_length=4)
    started_on: str | None = None
    ended_on: str | None = None
    note: str | None = Field(default=None, max_length=200)
    status: str | None = None


class MedicationPlanList(BaseModel):
    records: list[MedicationPlanOut]
