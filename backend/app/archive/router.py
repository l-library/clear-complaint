"""档案路由：体征、用药与用药计划。前缀只在 main.py 出现一次。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.account import service as account_service
from app.account.models import User
from app.archive import schema, service
from app.common.api import ApiResponse, ok
from app.db.session import get_session

router = APIRouter(tags=["archive"])

CurrentUser = Annotated[User, Depends(account_service.get_current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/vitals")
async def list_vitals(
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[schema.VitalPage]:
    data = await service.list_vitals(session, user.id, kind, page, size)
    return ok(schema.VitalPage(**data))


@router.post("/vitals")
async def create_vital(
    payload: schema.VitalRequest, session: SessionDep, user: CurrentUser
) -> ApiResponse[schema.VitalOut]:
    values = {
        "height_cm": payload.height_cm,
        "weight_kg": payload.weight_kg,
        "systolic": payload.systolic,
        "diastolic": payload.diastolic,
        "pulse": payload.pulse,
    }
    vital = await service.create_vital(session, user.id, payload.kind, payload.measured_at, values)
    return ok(schema.VitalOut(**vital))


@router.put("/vitals/{vital_id}")
async def update_vital(
    vital_id: int,
    payload: schema.VitalUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ApiResponse[schema.VitalOut]:
    values = {
        "height_cm": payload.height_cm,
        "weight_kg": payload.weight_kg,
        "systolic": payload.systolic,
        "diastolic": payload.diastolic,
        "pulse": payload.pulse,
        "measured_at": payload.measured_at,
    }
    vital = await service.update_vital(
        session, user.id, vital_id, values, set(payload.model_fields_set)
    )
    return ok(schema.VitalOut(**vital))


@router.delete("/vitals/{vital_id}")
async def delete_vital(vital_id: int, session: SessionDep, user: CurrentUser) -> ApiResponse[None]:
    await service.delete_vital(session, user.id, vital_id)
    return ok(None)


@router.get("/medications")
async def list_medications(
    session: SessionDep,
    user: CurrentUser,
    kind: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> ApiResponse[schema.MedicationList]:
    data = await service.list_medications(session, user.id, kind, status)
    return ok(schema.MedicationList(**data))


@router.post("/medications")
async def create_medication(
    payload: schema.MedicationRequest, session: SessionDep, user: CurrentUser
) -> ApiResponse[schema.MedicationOut]:
    medication = await service.create_medication(
        session,
        user.id,
        payload.name,
        payload.dosage_text,
        payload.frequency_text,
        payload.kind,
        payload.started_on,
        payload.ended_on,
    )
    return ok(schema.MedicationOut(**medication))


@router.put("/medications/{medication_id}")
async def update_medication(
    medication_id: int,
    payload: schema.MedicationUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ApiResponse[schema.MedicationOut]:
    medication = await service.update_medication(
        session,
        user.id,
        medication_id,
        payload.model_dump(),
        set(payload.model_fields_set),
    )
    return ok(schema.MedicationOut(**medication))


@router.delete("/medications/{medication_id}")
async def delete_medication(
    medication_id: int, session: SessionDep, user: CurrentUser
) -> ApiResponse[None]:
    await service.delete_medication(session, user.id, medication_id)
    return ok(None)


@router.get("/medication-plans")
async def list_plans(
    session: SessionDep, user: CurrentUser
) -> ApiResponse[schema.MedicationPlanList]:
    data = await service.list_plans(session, user.id)
    return ok(schema.MedicationPlanList(**data))


@router.post("/medication-plans")
async def create_plan(
    payload: schema.MedicationPlanRequest, session: SessionDep, user: CurrentUser
) -> ApiResponse[schema.MedicationPlanOut]:
    plan = await service.create_plan(
        session,
        user.id,
        payload.medication_id,
        payload.times,
        payload.started_on,
        payload.ended_on,
        payload.note,
    )
    return ok(schema.MedicationPlanOut(**plan))


@router.put("/medication-plans/{plan_id}")
async def update_plan(
    plan_id: int,
    payload: schema.MedicationPlanUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> ApiResponse[schema.MedicationPlanOut]:
    plan = await service.update_plan(
        session, user.id, plan_id, payload.model_dump(), set(payload.model_fields_set)
    )
    return ok(schema.MedicationPlanOut(**plan))


@router.delete("/medication-plans/{plan_id}")
async def delete_plan(plan_id: int, session: SessionDep, user: CurrentUser) -> ApiResponse[None]:
    await service.delete_plan(session, user.id, plan_id)
    return ok(None)
