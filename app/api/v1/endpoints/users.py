from fastapi import APIRouter, Depends
from typing import List
from src.schemas.user import PatientStatusSchema
from src.services.user_service import list_patients, get_patient_by_id
from app.api.deps import get_current_active_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=List[PatientStatusSchema])
def read_users(current_user: dict = Depends(get_current_active_user)):
    return list_patients()


@router.get("/{user_id}", response_model=PatientStatusSchema)
def read_user(user_id: str, current_user: dict = Depends(get_current_active_user)):
    return get_patient_by_id(user_id)
