from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.models import RuleEvaluationResponse, TelemetryPayload
from src.services.repository import update_patient_telemetry
from src.services.rule_engine import evaluate_rules

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post(
    "",
    response_model=RuleEvaluationResponse,
    summary="Ingest telemetry reading",
    description=(
        "Ingests a telemetry reading from a medical device (ECG, pulse oximeter, blood pressure monitor). "
        "The reading is stored and immediately evaluated against all active monitoring rules. "
        "If any rule triggers, the response includes the triggered rules and alerts are generated."
    ),
)
def ingest_telemetry_route(payload: TelemetryPayload):
    # Normalise both sides to UTC-aware datetimes for a safe comparison
    now_utc = datetime.now(timezone.utc)
    ts = payload.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts > now_utc:
        raise HTTPException(status_code=400, detail="timestamp cannot be in the future")

    update_patient_telemetry(payload)
    triggered_alerts = evaluate_rules(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered_alerts),
        triggered_rules=[],
    )