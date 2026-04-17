import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Response

from src.models import (
    RuleCreateRequest,
    RuleDefinition,
    RuleEvaluationResponse,
    RuleUpdateRequest,
    TelemetryPayload,
)
from src.services.rule_engine import evaluate_rules, get_rules

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get(
    "",
    response_model=List[RuleDefinition],
    summary="List active monitoring rules",
    description="Returns all configured monitoring rules with their expressions and severity levels.",
)
def list_rules():
    return get_rules()


@router.post(
    "",
    response_model=RuleDefinition,
    status_code=201,
    summary="Create a new monitoring rule",
    description="Creates a new rule that will be evaluated against incoming telemetry data.",
)
def create_rule(body: RuleCreateRequest):
    # TODO: persist to database
    new_rule = RuleDefinition(
        rule_id=str(uuid.uuid4()),
        name=body.name,
        description=body.description,
        expression=body.expression,
        severity=body.severity,
        enabled=True,
    )
    return new_rule


@router.get(
    "/{rule_id}",
    response_model=RuleDefinition,
    summary="Get a rule by ID",
    description="Returns a single monitoring rule by its unique identifier.",
)
def get_rule(rule_id: str):
    rules = get_rules()
    for rule in rules:
        if rule.rule_id == rule_id:
            return rule
    raise HTTPException(status_code=404, detail="Rule not found")


@router.put(
    "/{rule_id}",
    response_model=RuleDefinition,
    summary="Update a monitoring rule",
    description="Updates an existing monitoring rule. Only provided fields are changed.",
)
def update_rule(rule_id: str, body: RuleUpdateRequest):
    rules = get_rules()
    for rule in rules:
        if rule.rule_id == rule_id:
            # TODO: persist changes to database
            if body.name is not None:
                rule.name = body.name
            if body.description is not None:
                rule.description = body.description
            if body.expression is not None:
                rule.expression = body.expression
            if body.severity is not None:
                rule.severity = body.severity
            if body.enabled is not None:
                rule.enabled = body.enabled
            return rule
    raise HTTPException(status_code=404, detail="Rule not found")


@router.delete(
    "/{rule_id}",
    status_code=204,
    summary="Delete a monitoring rule",
    description="Deletes (or disables) a monitoring rule by its ID.",
)
def delete_rule(rule_id: str):
    rules = get_rules()
    for rule in rules:
        if rule.rule_id == rule_id:
            # TODO: remove from database
            return Response(status_code=204)
    raise HTTPException(status_code=404, detail="Rule not found")


@router.post(
    "/evaluate",
    response_model=RuleEvaluationResponse,
    summary="Evaluate telemetry against rules",
    description=(
        "Manually evaluates a telemetry payload against all active rules. "
        "Useful for testing rule configurations without storing the telemetry data."
    ),
)
def evaluate_rules_route(payload: TelemetryPayload):
    triggered_alerts = evaluate_rules(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered_alerts),
        triggered_rules=get_rules(),
    )
