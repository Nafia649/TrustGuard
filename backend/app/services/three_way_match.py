from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt


def perform_three_way_match(
    db: Session,
    payment: PaymentRequest,
    tolerance_percent: float = 2.0,
) -> Dict[str, Any]:
    """
    Executes the business logic verification of the Three-Way Match:
    1. Purchase Order existence and approval
    2. Goods Receipt (GRN) verification
    3. Vendor legitimacy and approval status
    4. Amount consistency within tolerance
    5. Duplicate invoice check
    6. Beneficiary bank account consistency

    IMPORTANT:
    These are deterministic BUSINESS FACTS.
    Three-way matching is NOT the ML fraud score.
    """
    # 1. Vendor check
    vendor = db.query(Vendor).filter(Vendor.vendor_id == payment.vendor_id).first()
    vendor_approved = 1 if (vendor and vendor.approved) else 0
    vendor_bank = vendor.bank_account if vendor else None

    # Bank account consistency check
    bank_match = bool(vendor and payment.bank_account == vendor_bank)
    bank_changed = 0 if bank_match else 1

    # 2. Purchase Order check
    po: Optional[PurchaseOrder] = None
    if payment.po_id:
        po = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.po_id == payment.po_id,
                PurchaseOrder.vendor_id == payment.vendor_id,
            )
            .first()
        )

    po_exists = 1 if po else 0
    po_approved = 1 if (po and po.status.upper() == "APPROVED") else 0

    # 3. Goods Receipt (GRN) check
    grn: Optional[GoodsReceipt] = None
    if po:
        grn = (
            db.query(GoodsReceipt)
            .filter(
                GoodsReceipt.po_id == po.po_id,
                GoodsReceipt.received.is_(True),
            )
            .first()
        )

    grn_exists = 1 if grn else 0
    goods_received = 1 if (grn and grn.received) else 0

    # 4. Amount matching and ratio calculation
    amount_match = False
    invoice_po_ratio: Optional[float] = None
    if po and po.amount > 0:
        invoice_po_ratio = round(payment.amount / po.amount, 4)
        pct_diff = abs(payment.amount - po.amount) / po.amount * 100.0
        amount_match = pct_diff <= tolerance_percent

    # 5. Duplicate invoice check
    duplicate_query = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.vendor_id == payment.vendor_id,
            PaymentRequest.invoice_id == payment.invoice_id,
            PaymentRequest.request_id != payment.request_id,
        )
        .first()
    )
    duplicate_invoice = 1 if duplicate_query else 0

    return {
        "po_exists": po_exists,
        "po_approved": po_approved,
        "grn_exists": grn_exists,
        "goods_received": goods_received,
        "vendor_approved": vendor_approved,
        "amount_match": amount_match,
        "invoice_po_amount_ratio": invoice_po_ratio,
        "duplicate_invoice": duplicate_invoice,
        "bank_account_match": bank_match,
        "bank_account_changed": bank_changed,
        "details": {
            "po_id": payment.po_id,
            "po_amount": po.amount if po else None,
            "invoice_amount": payment.amount,
            "tolerance_percent": tolerance_percent,
        },
    }
