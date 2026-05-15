from typing import List, Optional

from src.models import AlertSeverity, PatientStatus, RuleAlert, RuleDefinition, TelemetryPayload
from src.db.db import get_db_connection, is_db_available

# In-memory fallback when PostgreSQL cannot connect
PATIENT_STORE: dict[str, PatientStatus] = {}
ALERT_STORE: list[RuleAlert] = []
TELEMETRY_HISTORY: dict[str, list[TelemetryPayload]] = {}
RULE_STORE: dict[str, RuleDefinition] = {}


def _db_ready() -> bool:
    return is_db_available()


def _to_list(values):
    return list(values)


def initialize_default_rules():
    from src.models import AlertSeverity

    existing = get_rules()
    if existing:
        return

    for rule in [
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
    ]:
        try:
            add_rule(rule)
        except ValueError:
            pass


def get_rules() -> List[RuleDefinition]:
    if not _db_ready():
        return _to_list(RULE_STORE.values())

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT rule_id, name, description, expression, severity FROM rules")
        rows = cur.fetchall()

    return [
        RuleDefinition(
            rule_id=r["rule_id"],
            name=r["name"],
            description=r["description"] or "",
            expression=r["expression"],
            severity=AlertSeverity(r["severity"]),
        )
        for r in rows
    ]


def get_rule(rule_id: str) -> Optional[RuleDefinition]:
    if not _db_ready():
        return RULE_STORE.get(rule_id)

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT rule_id, name, description, expression, severity FROM rules WHERE rule_id = %s",
            (rule_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return RuleDefinition(
        rule_id=row["rule_id"],
        name=row["name"],
        description=row["description"] or "",
        expression=row["expression"],
        severity=AlertSeverity(row["severity"]),
    )


def add_rule(rule: RuleDefinition):
    if get_rule(rule.rule_id) is not None:
        raise ValueError(f"Rule with id {rule.rule_id} already exists")

    if not _db_ready():
        RULE_STORE[rule.rule_id] = rule
        return rule

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rules (rule_id, name, description, expression, severity) VALUES (%s, %s, %s, %s, %s)",
            (rule.rule_id, rule.name, rule.description, rule.expression, rule.severity.value),
        )
    return rule


def update_patient_telemetry(payload: TelemetryPayload):
    if not _db_ready():
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

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO patients (patient_id, last_seen, heart_rate, spo2, status) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (patient_id) DO UPDATE SET last_seen = EXCLUDED.last_seen, heart_rate = EXCLUDED.heart_rate, spo2 = EXCLUDED.spo2, status = EXCLUDED.status",
            (payload.patient_id, payload.timestamp, payload.heart_rate, payload.spo2, "stable"),
        )
        cur.execute(
            "INSERT INTO telemetry_history (patient_id, timestamp, heart_rate, spo2, systolic_bp, diastolic_bp, device_type, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                payload.patient_id,
                payload.timestamp,
                payload.heart_rate,
                payload.spo2,
                payload.systolic_bp,
                payload.diastolic_bp,
                payload.device_type.value if payload.device_type else None,
                payload.metadata,
            ),
        )

    return get_patient_status(payload.patient_id)


def get_patient_status(patient_id: str):
    if not _db_ready():
        return PATIENT_STORE.get(patient_id)

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT patient_id, last_seen, heart_rate, spo2, status FROM patients WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()

    if not row:
        return None
    return PatientStatus(
        patient_id=row["patient_id"],
        last_seen=row["last_seen"],
        heart_rate=row["heart_rate"],
        spo2=row["spo2"],
        status=row["status"],
        active_alerts=[],
    )


def list_patients():
    if not _db_ready():
        return _to_list(PATIENT_STORE.values())

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT patient_id, last_seen, heart_rate, spo2, status FROM patients")
        rows = cur.fetchall()

    return [
        PatientStatus(
            patient_id=r["patient_id"],
            last_seen=r["last_seen"],
            heart_rate=r["heart_rate"],
            spo2=r["spo2"],
            status=r["status"],
            active_alerts=[],
        )
        for r in rows
    ]


def add_alert(alert: RuleAlert):
    if not _db_ready():
        ALERT_STORE.append(alert)
        if alert.patient_id in PATIENT_STORE:
            PATIENT_STORE[alert.patient_id].active_alerts.append(alert)
        return

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO alerts (alert_id, patient_id, observed_at, rule, severity, message, tags) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            "ON CONFLICT (alert_id) DO NOTHING",
            (
                alert.alert_id,
                alert.patient_id,
                alert.observed_at,
                alert.rule,
                alert.severity.value,
                alert.message,
                alert.tags,
            ),
        )


def list_alerts(severity: Optional[AlertSeverity] = None):
    if not _db_ready():
        results = ALERT_STORE
        if severity:
            results = [a for a in ALERT_STORE if a.severity == severity]
        return results

    conn = get_db_connection()
    with conn.cursor() as cur:
        if severity:
            cur.execute(
                "SELECT alert_id, patient_id, observed_at, rule, severity, message, tags FROM alerts WHERE severity = %s",
                (severity.value,),
            )
        else:
            cur.execute("SELECT alert_id, patient_id, observed_at, rule, severity, message, tags FROM alerts")
        rows = cur.fetchall()

    return [
        RuleAlert(
            alert_id=r["alert_id"],
            patient_id=r["patient_id"],
            observed_at=r["observed_at"],
            rule=r["rule"],
            severity=AlertSeverity(r["severity"]),
            message=r["message"],
            tags=r["tags"] or [],
        )
        for r in rows
    ]


def get_telemetry_history(patient_id: str):
    if not _db_ready():
        return TELEMETRY_HISTORY.get(patient_id, [])

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT patient_id, timestamp, heart_rate, spo2, systolic_bp, diastolic_bp, device_type, metadata "
            "FROM telemetry_history WHERE patient_id = %s ORDER BY timestamp ASC",
            (patient_id,),
        )
        rows = cur.fetchall()

    return [
        TelemetryPayload(
            patient_id=r["patient_id"],
            timestamp=r["timestamp"],
            heart_rate=r["heart_rate"],
            spo2=r["spo2"],
            systolic_bp=r["systolic_bp"],
            diastolic_bp=r["diastolic_bp"],
            device_type=r["device_type"],
            metadata=r["metadata"],
        )
        for r in rows
    ]

