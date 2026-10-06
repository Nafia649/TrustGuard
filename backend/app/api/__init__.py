from app.api.health import router as health_router
from app.api.seed import router as seed_router
from app.api.payments import router as payments_router
from app.api.vendors import router as vendors_router

__all__ = [
    "health_router",
    "seed_router",
    "payments_router",
    "vendors_router",
]
