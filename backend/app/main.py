from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
import app.models  # Ensure all models are registered with Base.metadata
from app.api.health import router as health_router

# Create SQLite database tables if they do not exist
Base.metadata.create_all(bind=engine)

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
