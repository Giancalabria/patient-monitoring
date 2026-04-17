from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.models import AcknowledgeRequest, AlertSeverity, EmergencyNotification, RuleAlert
from src.services.repository import list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=List[RuleAlert],
    summary="List alerts",
    description="Returns all generated alerts. Supports filtering by severity, patient, and acknowledgement status.",
)
def list_alerts_route(
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity level"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledgement status"),
):
    alerts = list_alerts()
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    if patient_id:
        alerts = [a for a in alerts if a.patient_id == patient_id]
    if acknowledged is not None:
        alerts = [a for a in alerts if a.acknowledged == acknowledged]
    return alerts


@router.get(
    "/{alert_id}",
    response_model=RuleAlert,
    summary="Get alert by ID",
    description="Returns a single alert by its unique identifier.",
)
def get_alert(alert_id: str):
    alerts = list_alerts()
    for alert in alerts:
        if alert.alert_id == alert_id:
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


@router.put(
    "/{alert_id}/acknowledge",
    response_model=RuleAlert,
    summary="Acknowledge an alert",
    description="Marks an alert as acknowledged by a nurse or doctor. Records who acknowledged it and when.",
)
def acknowledge_alert(alert_id: str, body: AcknowledgeRequest):
    alerts = list_alerts()
    for alert in alerts:
        if alert.alert_id == alert_id:
            alert.acknowledged = True
            alert.acknowledged_by = body.acknowledged_by
            alert.acknowledged_at = datetime.utcnow()
            return alert
    raise HTTPException(status_code=404, detail="Alert not found")


@router.post(
    "/emergency",
    response_model=EmergencyNotification,
    summary="Send emergency event",
    description=(
        "Emits a high-priority emergency notification. "
        "Publishes a `monitoring.code_red` event to the SNS topic `monitoring-events`, "
        "consumed by M6 (Internación) and M8 (Portal del Paciente)."
    ),
)
def send_emergency(notification: EmergencyNotification):
    # TODO: publish monitoring.code_red event to SNS
    return notification
