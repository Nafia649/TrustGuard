from fastapi import APIRouter
from app.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint confirming backend service operational status."""
    return HealthResponse(
        status="ok",
        service="trustguard-backend",
        demo_mode=settings.DEMO_MODE,
    )
