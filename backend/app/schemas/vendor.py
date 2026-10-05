from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class VendorBase(BaseModel):
    vendor_id: str
    vendor_name: str
    approved: bool = True
    bank_account: str
    onboarded_date: Optional[datetime] = None
    usual_amount_mean: float = 0.0
    usual_amount_std: float = 0.0
    usual_hour: float = 12.0
    usual_weekday: int = 2


class VendorCreate(VendorBase):
    pass


class VendorResponse(VendorBase):
    model_config = ConfigDict(from_attributes=True)
