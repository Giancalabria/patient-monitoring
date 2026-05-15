from fastapi import APIRouter, HTTPException
from src.models import RuleDefinition, RuleEvaluationResponse, TelemetryPayload
from src.services.rule_engine import evaluate_rules, get_rules
from src.services.repository import add_rule, get_rule

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleDefinition], summary="Get active rules")
def list_rules():
    return get_rules()


@router.post("", response_model=RuleDefinition, summary="Add a new rule")
def create_rule(rule: RuleDefinition):
    existing = get_rule(rule.rule_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Rule {rule.rule_id} already exists")
    return add_rule(rule)


@router.post("/evaluate", response_model=RuleEvaluationResponse, summary="Evaluate telemetry against rules")
def evaluate_rules_route(payload: TelemetryPayload):
    triggered_alerts = evaluate_rules(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered_alerts),
        triggered_rules=[r for r in get_rules() if r.rule_id in {a.rule for a in triggered_alerts}],
    )
