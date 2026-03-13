from datetime import datetime, timedelta
from typing import List

from src.models import AlertSeverity, RuleAlert, RuleDefinition, TelemetryPayload
from src.services.repository import get_telemetry_history, add_alert

DEFAULT_RULES: List[RuleDefinition] = [
    RuleDefinition(
        rule_id="hr_high_2m",
        name="HR above 120 for 2 minutes",
        description="Genera alerta si HR > 120 durante al menos 2 minutos seguidos.",
        expression="heart_rate > 120 for 2 minutes",
        severity=AlertSeverity.CRITICAL,
    ),
    RuleDefinition(
        rule_id="spo2_low",
        name="SpO2 below 90",
        description="Genera alerta si SpO2 cae por debajo de 90%.",
        expression="spo2 < 90",
        severity=AlertSeverity.WARNING,
    ),
]


def evaluate_rules(payload: TelemetryPayload) -> List[RuleAlert]:
    triggered = []
    # Rule: SpO2 low
    if payload.spo2 < 90:
        triggered.append(
            RuleAlert(
                alert_id=f"spo2_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
                patient_id=payload.patient_id,
                observed_at=payload.timestamp,
                rule="spo2_low",
                severity=AlertSeverity.WARNING,
                message=f"SpO2 baja: {payload.spo2}%.",
                tags=["spo2", "physiological"],
            )
        )
    # Rule: HR > 120 for 2 minutes
    if payload.heart_rate > 120:
        history = get_telemetry_history(payload.patient_id)
        window_start = payload.timestamp - timedelta(minutes=2)
        high_count = sum(1 for t in history if t.timestamp >= window_start and t.heart_rate > 120)
        # check if there are at least 3+ points in 2 minutes for simulation
        if high_count >= 3:
            triggered.append(
                RuleAlert(
                    alert_id=f"hr120_{payload.patient_id}_{int(payload.timestamp.timestamp())}",
                    patient_id=payload.patient_id,
                    observed_at=payload.timestamp,
                    rule="hr_high_2m",
                    severity=AlertSeverity.CRITICAL,
                    message=f"HR sostenida >120 por al menos 2 minutos (últimos {high_count} muestras).",
                    tags=["heart_rate", "critical"],
                )
            )

    for a in triggered:
        add_alert(a)
    return triggered


def get_rules():
    return DEFAULT_RULES
