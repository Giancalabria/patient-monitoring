from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.models import PatientStatus, TelemetryPayload
from src.services.repository import get_patient_status, get_telemetry_history, list_patients

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get(
    "",
    response_model=List[PatientStatus],
    summary="List all monitored patients",
    description="Returns the current monitoring status of every active patient.",
)
def list_patients_route():
    return list_patients()


@router.get(
    "/{patient_id}/status",
    response_model=PatientStatus,
    summary="Get patient monitoring status",
    description="Returns the current monitoring status of a single patient including latest vitals and active alerts.",
)
def patient_status(patient_id: str):
    patient = get_patient_status(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get(
    "/{patient_id}/telemetry",
    response_model=List[TelemetryPayload],
    summary="Get patient telemetry history",
    description="Returns the telemetry reading history for a patient. Supports optional time range and limit filters.",
)
def patient_telemetry_history(
    patient_id: str,
    from_dt: Optional[datetime] = Query(None, alias="from", description="Start of time range (ISO 8601)"),
    to_dt: Optional[datetime] = Query(None, alias="to", description="End of time range (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of readings to return"),
):
    history = get_telemetry_history(patient_id)
    if from_dt:
        history = [t for t in history if t.timestamp >= from_dt]
    if to_dt:
        history = [t for t in history if t.timestamp <= to_dt]
    return history[:limit]
