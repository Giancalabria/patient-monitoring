"""
Rule engine powered by GoRules Zen Engine (JDM).

Rules are defined as JSON Decision Model files stored in ``data/rules/``.
Today they are loaded from disk; in the future the JSON will come from a
PostgreSQL database.

Temporal rules (e.g. "HR > 120 sustained for 2 minutes") are flagged
with ``needs_temporal_check: true`` in the decision-table output.  The
Python layer performs the time-window validation after Zen returns
its matches.
"""

from __future__ import annotations

import json
import os
from datetime import timedelta
from typing import Any, Dict, List

import zen

from src.models import AlertSeverity, RuleAlert, RuleDefinition, TelemetryPayload
from src.services.repository import add_alert, get_telemetry_history

# ── Paths ──────────────────────────────────────────────────────────────

_RULES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "rules")
)
_VITAL_SIGNS_RULES_PATH = os.path.join(_RULES_DIR, "vital_signs_rules.json")

# ── Zen Engine initialisation ──────────────────────────────────────────

_engine = zen.ZenEngine()


def _load_decision(path: str) -> zen.ZenDecision:
    """Load a JDM JSON file and create a Zen decision."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return _engine.create_decision(content)


_vital_signs_decision: zen.ZenDecision = _load_decision(_VITAL_SIGNS_RULES_PATH)


def reload_rules() -> None:
    """Reload rule definitions from disk (or, in the future, from the DB).

    Call this after updating the JSON files to pick up changes without
    restarting the server.
    """
    global _vital_signs_decision
    _vital_signs_decision = _load_decision(_VITAL_SIGNS_RULES_PATH)


# ── Temporal validators ────────────────────────────────────────────────

_TEMPORAL_VALIDATORS: Dict[str, Any] = {}


def _validate_hr_high_2m(payload: TelemetryPayload) -> bool:
    """Return True if HR > 120 has been sustained for >= 2 minutes."""
    history = get_telemetry_history(payload.patient_id)
    window_start = payload.timestamp - timedelta(minutes=2)
    high_count = sum(
        1
        for t in history
        if t.timestamp >= window_start
        and t.heart_rate is not None
        and t.heart_rate > 120
    )
    return high_count >= 3


_TEMPORAL_VALIDATORS["hr_high_2m"] = _validate_hr_high_2m

# ── Public API ─────────────────────────────────────────────────────────


def evaluate_rules(payload: TelemetryPayload) -> List[RuleAlert]:
    """Evaluate all Zen rules against a telemetry payload.

    1. Build an input dict from the payload (only non-None vitals).
    2. Run the Zen decision table (``collect`` hit-policy → list of matches).
    3. For each match flagged ``needs_temporal_check``, run the corresponding
       Python validator.  If the validator returns False the match is discarded.
    4. Convert surviving matches into ``RuleAlert`` objects and persist them.
    """

    # Build context for Zen — only include vitals that are present
    context: Dict[str, Any] = {}
    if payload.heart_rate is not None:
        context["heart_rate"] = payload.heart_rate
    if payload.spo2 is not None:
        context["spo2"] = payload.spo2
    if payload.systolic_bp is not None:
        context["systolic_bp"] = payload.systolic_bp
    if payload.diastolic_bp is not None:
        context["diastolic_bp"] = payload.diastolic_bp
    if payload.respiratory_rate is not None:
        context["respiratory_rate"] = payload.respiratory_rate
    if payload.temperature is not None:
        context["temperature"] = payload.temperature
    if payload.gcs is not None:
        context["gcs"] = payload.gcs

    # Evaluate the Zen decision table
    result = _vital_signs_decision.evaluate(context)

    # The decision table uses `collect` hit-policy → result is a list
    matches: List[Dict[str, Any]] = result.get("result", [])
    if isinstance(matches, dict):
        # Single match returned as dict instead of list
        matches = [matches]

    triggered: List[RuleAlert] = []

    for match in matches:
        rule_id: str = match.get("rule_id", "unknown")
        needs_temporal = match.get("needs_temporal_check", False)

        # If the rule requires temporal validation, run the Python validator
        if needs_temporal:
            validator = _TEMPORAL_VALIDATORS.get(rule_id)
            if validator and not validator(payload):
                continue  # temporal condition not met — skip this match

        severity_str: str = match.get("severity", "info")
        severity = AlertSeverity(severity_str)
        message: str = match.get("message", "")
        tags: List[str] = match.get("tags", [])

        alert = RuleAlert(
            alert_id=f"{rule_id}_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
            patient_id=payload.patient_id,
            observed_at=payload.timestamp,
            rule=rule_id,
            severity=severity,
            message=message,
            tags=tags,
        )
        triggered.append(alert)

    for a in triggered:
        add_alert(a)

    return triggered


def get_rules() -> List[RuleDefinition]:
    """Return the list of active rule definitions (derived from the JDM JSON).

    Reads the current decision-table content and converts each row into a
    ``RuleDefinition`` for the ``/rules`` API.
    """
    with open(_VITAL_SIGNS_RULES_PATH, "r", encoding="utf-8") as f:
        jdm = json.load(f)

    rules: List[RuleDefinition] = []
    for node in jdm.get("nodes", []):
        if node.get("type") != "decisionTableNode":
            continue
        content = node.get("content", {})
        input_fields = {inp["id"]: inp for inp in content.get("inputs", [])}
        output_fields = {out["id"]: out for out in content.get("outputs", [])}

        for row in content.get("rules", []):
            row_id = row.get("_id", "unknown")
            description = row.get("_description", "")

            # Build a human-readable expression from non-empty input cells
            expression_parts: List[str] = []
            for inp_id, inp_meta in input_fields.items():
                cell_value = row.get(inp_id, "")
                if cell_value:
                    field_name = inp_meta.get("field", inp_meta.get("name", inp_id))
                    expression_parts.append(f"{field_name} {cell_value}")
            expression = " AND ".join(expression_parts) if expression_parts else "always"

            # Extract severity from the output cell
            severity_cell = row.get(
                next(
                    (oid for oid, om in output_fields.items() if om.get("field") == "severity"),
                    "",
                ),
                "\"info\"",
            )
            severity_str = severity_cell.strip('"')
            severity = AlertSeverity(severity_str) if severity_str in AlertSeverity.__members__.values() else AlertSeverity.INFO

            rules.append(
                RuleDefinition(
                    rule_id=row_id,
                    name=description or row_id,
                    description=description,
                    expression=expression,
                    severity=severity,
                    enabled=True,
                )
            )

    return rules
