from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
import app.models  # Ensure all models are registered with Base.metadata
from app.api.health import router as health_router
from app.api.seed import router as seed_router
from app.api.payments import router as payments_router
from app.api.vendors import router as vendors_router
from app.api.scoring import router as scoring_router
from app.api.policy import router as policy_router
from app.api.signing import router as signing_router
from app.api.webauthn import router as webauthn_router
from app.api.audit import router as audit_router

from app.services.migration_service import init_db

# Create SQLite database tables if they do not exist and apply schema migrations
init_db(engine)

app = FastAPI(
    title="TrustGuard + REALKEY API",
    description=(
        "Payment-authorization control layer orchestrating ML fraud risk analysis "
        "and REALKEY cryptographic WebAuthn approvals. "
        "NOTE: Built for hackathon MVP - simulated banking/ledger layer."
    ),
    version="1.0.0",
)

# Configure Cross-Origin Resource Sharing (CORS) for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(health_router)
app.include_router(seed_router)
app.include_router(payments_router)
app.include_router(vendors_router)
app.include_router(scoring_router)
app.include_router(policy_router)
app.include_router(signing_router)
app.include_router(webauthn_router)
app.include_router(audit_router)


@app.get("/", tags=["Root"])
def root():
    """Root info endpoint directing to documentation."""
    return {
        "service": "TrustGuard + REALKEY API",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "demo_mode": settings.DEMO_MODE,
    }
