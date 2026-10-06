from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.seed_service import seed_database

router = APIRouter(tags=["Seed"])


@router.post("/seed", status_code=200)
def seed(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Populate the database with deterministic demo data for Acme Ltd.
    Resets tables and injects standard vendors, purchase orders, approvers,
    default policy v1, and 4 scenario payment requests.
    """
    return seed_database(db)
