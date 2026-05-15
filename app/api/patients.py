from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.models import PatientStatus, TelemetryPayload, StartMonitoringRequest, StopMonitoringRequest, MonitoringResponse
from src.services.repository import (
    get_patient_status,
    get_telemetry_history,
    list_patients,
    activate_monitoring,
    deactivate_monitoring,
    is_monitoring_active,
)

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


@router.post(
    "/monitor",
    response_model=MonitoringResponse,
    status_code=201,
    summary="Activate patient monitoring",
    description="Start monitoring a patient at a specific bed. This endpoint is consumed by the Internación module (M6) when a patient is admitted.",
)
def start_monitoring(body: StartMonitoringRequest):
    if is_monitoring_active(body.patient_id):
        raise HTTPException(
            status_code=409,
            detail=f"Patient {body.patient_id} is already being monitored",
        )

    activate_monitoring(body.patient_id, body.bed_id)
    return MonitoringResponse(
        patient_id=body.patient_id,
        bed_id=body.bed_id,
        monitoring=True,
        message=f"Monitoring activated for patient {body.patient_id} at bed {body.bed_id}",
    )


@router.post(
    "/monitor/stop",
    response_model=MonitoringResponse,
    summary="Stop patient monitoring",
    description="Stop monitoring a patient. This endpoint is consumed by the Internación module (M6) when a patient is discharged.",
)
def stop_monitoring(body: StopMonitoringRequest):
    if not is_monitoring_active(body.patient_id):
        raise HTTPException(
            status_code=404,
            detail=f"Patient {body.patient_id} is not currently being monitored",
        )

    deactivate_monitoring(body.patient_id)
    return MonitoringResponse(
        patient_id=body.patient_id,
        monitoring=False,
        message=f"Monitoring stopped for patient {body.patient_id}",
    )
