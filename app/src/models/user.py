from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class DeviceType(str, Enum):
    ECG = "ecg"
    PULSE_OX = "pulse_ox"
    BP = "blood_pressure"
    VENTILATOR = "ventilator"
    TEMP_SENSOR = "temperature_sensor"
    MULTI_PARAM = "multi_parameter"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class BedType(str, Enum):
    UTI = "UTI"
    UCO = "UCO"
    SALA_COMUN = "sala_comun"
    NEONATOLOGIA = "neonatologia"
    GUARDIA = "guardia"


# ── Telemetry ──────────────────────────────────────────────────────────

class TelemetryPayload(BaseModel):
    """Payload received from a medical device sensor reading."""
    patient_id: str = Field(..., description="Patient identifier", examples=["P001"])
    device_id: str = Field(..., description="Unique device/sensor identifier", examples=["ECG-UTI-001"])
    device_type: DeviceType = Field(DeviceType.MULTI_PARAM, description="Type of medical device")
    timestamp: datetime = Field(..., description="Reading timestamp in ISO 8601 UTC")

    # Cardiac
    heart_rate: Optional[int] = Field(None, ge=0, le=300, description="Heart rate in BPM")
    spo2: Optional[float] = Field(None, ge=0, le=100, description="Oxygen saturation percentage")
    systolic_bp: Optional[int] = Field(None, ge=0, le=300, description="Systolic blood pressure (mmHg)")
    diastolic_bp: Optional[int] = Field(None, ge=0, le=200, description="Diastolic blood pressure (mmHg)")

    # Respiratory
    respiratory_rate: Optional[int] = Field(None, ge=0, le=80, description="Breaths per minute")
    etco2: Optional[float] = Field(None, ge=0, le=100, description="End-tidal CO2 (mmHg)")
    fio2: Optional[float] = Field(None, ge=0.21, le=1.0, description="Fraction of inspired oxygen (0.21–1.0)")

    # Temperature
    temperature: Optional[float] = Field(None, ge=30.0, le=45.0, description="Body temperature in °C")

    # ECG specific
    rhythm: Optional[str] = Field(None, description="ECG rhythm classification (e.g. sinus, afib, vtach)")
    qt_interval: Optional[int] = Field(None, description="QT interval in milliseconds")

    # Consciousness
    gcs: Optional[int] = Field(None, ge=3, le=15, description="Glasgow Coma Scale (3–15)")

    # Metadata
    bed_id: Optional[str] = Field(None, description="Bed identifier where the patient is located", examples=["UTI-A-03"])
    ward: Optional[str] = Field(None, description="Ward or sector name", examples=["UTI-A"])
    metadata: Optional[Dict[str, str]] = Field(None, description="Free-form key-value pairs for extra device info")


# ── Patient ────────────────────────────────────────────────────────────

class PatientInfo(BaseModel):
    """Static patient demographic information (loaded from master data)."""
    patient_id: str = Field(..., description="Patient identifier")
    first_name: str
    last_name: str
    dni: str = Field(..., description="Documento Nacional de Identidad")
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    sex: str = Field(..., description="M or F")
    blood_type: Optional[str] = Field(None, description="Blood type (e.g. A+, O-)")
    admission_id: Optional[str] = Field(None, description="Current admission ID from M6 Internación")
    bed_id: Optional[str] = Field(None, description="Current bed assignment")
    bed_type: Optional[BedType] = Field(None, description="Type of bed (UTI, UCO, sala_comun, etc.)")
    ward: Optional[str] = Field(None, description="Ward or sector")
    attending_physician: Optional[str] = Field(None, description="Name of the attending physician")
    diagnosis: Optional[str] = Field(None, description="Primary diagnosis")
    allergies: Optional[str] = Field(None, description="Known allergies")


class PatientStatus(BaseModel):
    """Real-time monitoring status of a patient."""
    patient_id: str
    patient_info: Optional[PatientInfo] = Field(None, description="Patient demographic info (if available)")
    last_seen: datetime = Field(..., description="Timestamp of the last telemetry reading")

    # Latest vitals
    heart_rate: Optional[int] = Field(None, description="Latest heart rate (BPM)")
    spo2: Optional[float] = Field(None, description="Latest SpO2 (%)")
    systolic_bp: Optional[int] = Field(None, description="Latest systolic BP (mmHg)")
    diastolic_bp: Optional[int] = Field(None, description="Latest diastolic BP (mmHg)")
    respiratory_rate: Optional[int] = Field(None, description="Latest respiratory rate (breaths/min)")
    temperature: Optional[float] = Field(None, description="Latest body temperature (°C)")
    gcs: Optional[int] = Field(None, description="Latest Glasgow Coma Scale")

    # Status
    status: str = Field("stable", description="stable | warning | critical")
    bed_id: Optional[str] = Field(None, description="Current bed")
    ward: Optional[str] = Field(None, description="Current ward")
    active_alerts: List["RuleAlert"] = []


# ── Alerts ─────────────────────────────────────────────────────────────

class RuleAlert(BaseModel):
    alert_id: str
    patient_id: str
    observed_at: datetime
    rule: str = Field(..., description="Rule ID that triggered this alert")
    severity: AlertSeverity
    message: str
    tags: List[str] = []
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = Field(..., description="User ID of the nurse or doctor acknowledging the alert")
    notes: Optional[str] = Field(None, description="Optional notes about the acknowledgement")


class EmergencyNotification(BaseModel):
    patient_id: str
    bed_id: Optional[str] = Field(None, description="Bed where the patient is located")
    code: str = Field(..., description="Emergency code, e.g. CODE_RED, CODE_BLUE")
    reason: str
    triggered_at: datetime
    severity: AlertSeverity = AlertSeverity.CRITICAL


# ── Rules ──────────────────────────────────────────────────────────────

class RuleDefinition(BaseModel):
    rule_id: str
    name: str
    description: str
    expression: str = Field(..., description="Rule expression (e.g. 'heart_rate > 120 for 2 minutes')")
    severity: AlertSeverity
    enabled: bool = True


class RuleCreateRequest(BaseModel):
    name: str
    description: str
    expression: str
    severity: AlertSeverity


class RuleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    enabled: Optional[bool] = None


class RuleEvaluationResponse(BaseModel):
    patient_id: str
    telemetry: TelemetryPayload
    triggered: bool
    triggered_rules: List[RuleDefinition]


# Rebuild forward refs for PatientStatus -> RuleAlert
PatientStatus.model_rebuild()
