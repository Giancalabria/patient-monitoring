from typing import Dict, List
from src.models.user import PatientStatus, RuleAlert, TelemetryPayload

PATIENT_STORE: Dict[str, PatientStatus] = {}
TELEMETRY_HISTORY: Dict[str, List[TelemetryPayload]] = {}
ALERTS: List[RuleAlert] = []


def save_telemetry(payload: TelemetryPayload) -> PatientStatus:
    status = PatientStatus(
        patient_id=payload.patient_id,
        last_seen=payload.timestamp,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        status="stable",
        active_alerts=[],
    )
    PATIENT_STORE[payload.patient_id] = status
    TELEMETRY_HISTORY.setdefault(payload.patient_id, []).append(payload)
    return status


def get_patient_status(patient_id: str):
    return PATIENT_STORE.get(patient_id)


def list_patients():
    return list(PATIENT_STORE.values())


def get_telemetry_history(patient_id: str):
    return TELEMETRY_HISTORY.get(patient_id, [])


def add_alert(alert: RuleAlert):
    ALERTS.append(alert)
    if alert.patient_id in PATIENT_STORE:
        PATIENT_STORE[alert.patient_id].active_alerts.append(alert)


def list_alerts(severity: str = None):
    if severity:
        return [a for a in ALERTS if a.severity.value == severity]
    return ALERTS
