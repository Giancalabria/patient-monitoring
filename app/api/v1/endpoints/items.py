from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from src.models.user import TelemetryPayload, RuleEvaluationResponse, EmergencyNotification
from src.schemas.user import RuleAlertSchema, RuleDefinitionSchema
from src.services.user_service import ingest_telemetry, get_rules, evaluate_telemetry, list_alerts
from api.deps import get_current_active_user

router = APIRouter(prefix="/items", tags=["items"])


@router.post("/telemetry", response_model=RuleEvaluationResponse)
def post_telemetry(payload: TelemetryPayload, current_user: dict = Depends(get_current_active_user)):
    try:
        return ingest_telemetry(payload)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/rules", response_model=List[RuleDefinitionSchema])
def get_rule_definitions(current_user: dict = Depends(get_current_active_user)):
    return get_rules()


@router.post("/rules/evaluate", response_model=RuleEvaluationResponse)
def rule_evaluate(payload: TelemetryPayload, current_user: dict = Depends(get_current_active_user)):
    return evaluate_telemetry(payload)


@router.get("/alerts", response_model=List[RuleAlertSchema])
def get_all_alerts(severity: Optional[str] = None, current_user: dict = Depends(get_current_active_user)):
    return list_alerts(severity)


@router.post("/emergency", response_model=EmergencyNotification)
def emergency_event(notification: EmergencyNotification, current_user: dict = Depends(get_current_active_user)):
    return notification
