from datetime import datetime
from typing import Dict, List

from src.models import PatientStatus, RuleAlert, TelemetryPayload

# In-memory store for demo template
PATIENT_STORE: Dict[str, PatientStatus] = {}
ALERT_STORE: List[RuleAlert] = []
TELEMETRY_HISTORY: Dict[str, List[TelemetryPayload]] = {}


def update_patient_telemetry(payload: TelemetryPayload):
    now = payload.timestamp
    status = PatientStatus(
        patient_id=payload.patient_id,
        last_seen=now,
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


def add_alert(alert: RuleAlert):
    ALERT_STORE.append(alert)
    if alert.patient_id in PATIENT_STORE:
        PATIENT_STORE[alert.patient_id].active_alerts.append(alert)


def list_alerts():
    return ALERT_STORE


def get_telemetry_history(patient_id: str):
    return TELEMETRY_HISTORY.get(patient_id, [])
