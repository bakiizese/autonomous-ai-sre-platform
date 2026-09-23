from fastapi import APIRouter

from app.schemas.api import RateLimitStatusOut
from app.services import rate_limit_service

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/rate-limits", response_model=RateLimitStatusOut)
def rate_limit_status():
    return rate_limit_service.get_status()
