from datetime import datetime

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
    if payload.timestamp > datetime.utcnow():
        raise HTTPException(status_code=400, detail="timestamp cannot be in the future")

    update_patient_telemetry(payload)
    triggered_alerts = evaluate_rules(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered_alerts),
        triggered_rules=[],
    )
