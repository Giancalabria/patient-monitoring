from fastapi import APIRouter
from app.api.v1.endpoints import users, items

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)
router.include_router(items.router)
