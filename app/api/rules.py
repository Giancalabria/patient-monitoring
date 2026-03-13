from fastapi import APIRouter
from src.models import RuleDefinition, RuleEvaluationResponse, TelemetryPayload
from src.services.rule_engine import evaluate_rules, get_rules

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleDefinition], summary="Get active rules")
def list_rules():
    return get_rules()


@router.post("/evaluate", response_model=RuleEvaluationResponse, summary="Evaluate telemetry against rules")
def evaluate_rules_route(payload: TelemetryPayload):
    triggered_alerts = evaluate_rules(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered_alerts),
        triggered_rules=get_rules(),
    )
