from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import VendorResponse

router = APIRouter(tags=["Vendors"])


@router.get("/vendors", response_model=List[VendorResponse], summary="List all registered vendors")
def list_vendors(db: Session = Depends(get_db)):
    """Retrieve list of all simulated vendors in the database."""
    return db.query(Vendor).all()


@router.get("/vendors/{vendor_id}", response_model=VendorResponse, summary="Get vendor by ID")
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    """Retrieve details of a single vendor by ID."""
    vendor = db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_id}' not found.",
        )
    return vendor
