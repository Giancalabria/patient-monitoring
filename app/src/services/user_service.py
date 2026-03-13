from datetime import timedelta
from typing import Dict, List, Optional
from src.models.user import (
    EmergencyNotification,
    RuleAlert,
    RuleDefinition,
    RuleEvaluationResponse,
    TelemetryPayload,
    PatientStatus,
    AlertSeverity,
)
from src.repositories.user_repository import (
    add_alert,
    get_patient_status,
    list_patients as repo_list_patients,
    save_telemetry,
    list_alerts as repo_list_alerts,
    get_telemetry_history,
)

DEFAULT_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="hr_high_2m",
        name="HR above 120 for 2 minutes",
        description="HR > 120 for at least 2 minutes",
        expression="heart_rate > 120 for 2 minutes",
        severity=AlertSeverity.CRITICAL,
    ),
    RuleDefinition(
        rule_id="spo2_low",
        name="SpO2 below 90",
        description="SpO2 under 90%",
        expression="spo2 < 90",
        severity=AlertSeverity.WARNING,
    ),
]


def ingest_telemetry(payload: TelemetryPayload) -> RuleEvaluationResponse:
    if payload.timestamp > __import__("datetime").datetime.utcnow():
        raise ValueError("timestamp cannot be in the future")

    save_telemetry(payload)
    triggered = evaluate_telemetry(payload)
    return RuleEvaluationResponse(
        patient_id=payload.patient_id,
        telemetry=payload,
        triggered=bool(triggered),
        triggered_rules=triggered,
    )


def get_rules() -> List[RuleDefinition]:
    return DEFAULT_RULES


def evaluate_telemetry(payload: TelemetryPayload) -> List[RuleDefinition]:
    triggered: List[RuleDefinition] = []
    if payload.spo2 < 90:
        alert = RuleAlert(
            alert_id=f"spo2_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
            patient_id=payload.patient_id,
            observed_at=payload.timestamp,
            rule="spo2_low",
            severity=AlertSeverity.WARNING,
            message=f"SpO2 bajo: {payload.spo2}%",
            tags=["spo2"],
        )
        add_alert(alert)
        triggered.append(DEFAULT_RULES[1])

    if payload.heart_rate > 120:
        history = get_telemetry_history(payload.patient_id)
        window_start = payload.timestamp - timedelta(minutes=2)
        high_count = sum(1 for t in history if t.timestamp >= window_start and t.heart_rate > 120)
        if high_count >= 3:
            alert = RuleAlert(
                alert_id=f"hr_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
                patient_id=payload.patient_id,
                observed_at=payload.timestamp,
                rule="hr_high_2m",
                severity=AlertSeverity.CRITICAL,
                message="HR alta sostenida",
                tags=["heart_rate"],
            )
            add_alert(alert)
            triggered.append(DEFAULT_RULES[0])
    return triggered


def list_patients() -> List[PatientStatus]:
    return repo_list_patients()


def get_patient_by_id(patient_id: str) -> PatientStatus:
    patient = get_patient_status(patient_id)
    if not patient:
        raise ValueError("Patient not found")
    return patient


def list_alerts(severity: Optional[str] = None):
    alerts_data = repo_list_alerts()
    if severity:
        alerts_data = [a for a in alerts_data if a.severity.value == severity]
    return alerts_data
