from fastapi import APIRouter, HTTPException
from src.services.repository import get_patient_status, list_patients

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", summary="List all patients")
def list_patients_route():
    return list_patients()


@router.get("/{patient_id}/status", summary="Get patient status")
def patient_status(patient_id: str):
    patient = get_patient_status(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient

