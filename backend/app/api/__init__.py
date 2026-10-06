from app.api.health import router as health_router
from app.api.seed import router as seed_router
from app.api.payments import router as payments_router
from app.api.vendors import router as vendors_router
from app.api.scoring import router as scoring_router
from app.api.policy import router as policy_router
from app.api.signing import router as signing_router
from app.api.webauthn import router as webauthn_router
from app.api.audit import router as audit_router

__all__ = [
    "health_router",
    "seed_router",
    "payments_router",
    "vendors_router",
    "scoring_router",
    "policy_router",
    "signing_router",
    "webauthn_router",
    "audit_router",
]
