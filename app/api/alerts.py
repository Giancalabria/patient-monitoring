from fastapi import APIRouter, Query
from typing import Optional, List
from src.models import AlertSeverity, EmergencyNotification, RuleAlert
from src.services.repository import list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=List[RuleAlert], summary="List alerts")
def list_alerts_route(severity: Optional[AlertSeverity] = Query(None)):
    alerts = list_alerts()
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    return alerts


@router.post("/emergency", response_model=EmergencyNotification, summary="Send emergency event")
def send_emergency(notification: EmergencyNotification):
    return notification

