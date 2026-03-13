from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceType(str, Enum):
    ECG = "ecg"
    PULSE_OX = "pulse_ox"
    BP = "blood_pressure"


class TelemetryPayload(BaseModel):
    patient_id: str = Field(..., description="Patient ID")
    timestamp: datetime
    heart_rate: int
    spo2: float
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    device_type: DeviceType = DeviceType.ECG
    metadata: Optional[Dict[str, str]] = None


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RuleAlert(BaseModel):
    alert_id: str
    patient_id: str
    observed_at: datetime
    rule: str
    severity: AlertSeverity
    message: str
    tags: List[str] = []


class PatientStatus(BaseModel):
    patient_id: str
    last_seen: datetime
    heart_rate: int
    spo2: float
    status: str
    active_alerts: List[RuleAlert] = []


class EmergencyNotification(BaseModel):
    patient_id: str
    code: str
    reason: str
    triggered_at: datetime
    severity: AlertSeverity = AlertSeverity.CRITICAL


class RuleDefinition(BaseModel):
    rule_id: str
    name: str
    description: str
    expression: str
    severity: AlertSeverity


class RuleEvaluationResponse(BaseModel):
    patient_id: str
    telemetry: TelemetryPayload
    triggered: bool
    triggered_rules: List[RuleDefinition]
