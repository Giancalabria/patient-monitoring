import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

from src.models import PatientInfo, PatientStatus, RuleAlert, TelemetryPayload

# ── In-memory stores ───────────────────────────────────────────────────

PATIENT_INFO: Dict[str, PatientInfo] = {}
PATIENT_STORE: Dict[str, PatientStatus] = {}
ALERT_STORE: List[RuleAlert] = []
TELEMETRY_HISTORY: Dict[str, List[TelemetryPayload]] = {}


# ── CSV loader ─────────────────────────────────────────────────────────

def _load_patients_from_csv():
    """Load patient mock data from CSV and pre-populate the monitoring store."""
    csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "patients.csv")
    csv_path = os.path.normpath(csv_path)

    if not os.path.exists(csv_path):
        return

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            info = PatientInfo(
                patient_id=row["patient_id"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                dni=row["dni"],
                date_of_birth=row["date_of_birth"],
                sex=row["sex"],
                blood_type=row.get("blood_type") or None,
                admission_id=row.get("admission_id") or None,
                bed_id=row.get("bed_id") or None,
                bed_type=row.get("bed_type") or None,
                ward=row.get("ward") or None,
                attending_physician=row.get("attending_physician") or None,
                diagnosis=row.get("diagnosis") or None,
                allergies=row.get("allergies") or None,
            )
            PATIENT_INFO[info.patient_id] = info

            # Pre-populate monitoring status with no vitals yet
            PATIENT_STORE[info.patient_id] = PatientStatus(
                patient_id=info.patient_id,
                patient_info=info,
                last_seen=datetime.utcnow(),
                heart_rate=None,
                spo2=None,
                status="stable",
                bed_id=info.bed_id,
                ward=info.ward,
                active_alerts=[],
            )


# Load on module import
_load_patients_from_csv()


# ── Repository functions ───────────────────────────────────────────────

def update_patient_telemetry(payload: TelemetryPayload) -> PatientStatus:
    info = PATIENT_INFO.get(payload.patient_id)
    existing = PATIENT_STORE.get(payload.patient_id)

    status = PatientStatus(
        patient_id=payload.patient_id,
        patient_info=info,
        last_seen=payload.timestamp,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        systolic_bp=payload.systolic_bp,
        diastolic_bp=payload.diastolic_bp,
        respiratory_rate=payload.respiratory_rate,
        temperature=payload.temperature,
        gcs=payload.gcs,
        status="stable",
        bed_id=payload.bed_id or (existing.bed_id if existing else None),
        ward=payload.ward or (existing.ward if existing else None),
        active_alerts=existing.active_alerts if existing else [],
    )
    PATIENT_STORE[payload.patient_id] = status
    TELEMETRY_HISTORY.setdefault(payload.patient_id, []).append(payload)
    return status


def get_patient_status(patient_id: str) -> Optional[PatientStatus]:
    return PATIENT_STORE.get(patient_id)


def list_patients() -> List[PatientStatus]:
    return list(PATIENT_STORE.values())


def add_alert(alert: RuleAlert):
    ALERT_STORE.append(alert)
    if alert.patient_id in PATIENT_STORE:
        PATIENT_STORE[alert.patient_id].active_alerts.append(alert)


def list_alerts() -> List[RuleAlert]:
    return ALERT_STORE


def get_telemetry_history(patient_id: str) -> List[TelemetryPayload]:
    return TELEMETRY_HISTORY.get(patient_id, [])
