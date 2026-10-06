import json
from datetime import datetime, timedelta
from typing import Any, Dict
from sqlalchemy.orm import Session

from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.models.payment_request import PaymentRequest
from app.models.approver import Approver
from app.models.signature import Signature
from app.models.policy import PolicyVersion
from app.models.audit_log import AuditLog
from app.models.ledger import LedgerEntry
from app.services.audit_service import log_event


DEFAULT_POLICY_CONFIG = {
    "version": 1,
    "thresholds": {
        "auto_approve_below": 30.0,
        "one_signature_below": 70.0,
        "two_signature_below": 90.0,
    },
    "auto_approve_cap_amount": 50000.0,
    "monthly_auto_approved_cap_per_vendor": 200000.0,
    "signers": {
        "one_signature": ["senior_administrator"],
        "two_signatures": ["finance_head", "senior_executive"],
    },
    "always_escalate": ["new_vendor", "bank_detail_change"],
    "po_match_tolerance_percent": 2.0,
    "hold_time_limit_hours": 48,
    "windowed_total_days": 7,
}


def seed_database(db: Session) -> Dict[str, Any]:
    """
    Populates deterministic demo/seed data for Acme Ltd.
    Supports core hackathon demonstration scenarios:
    1. Low-risk auto-approval
    2. Medium-risk single signature
    3. Tamper-demo payload
    4. High-risk analyst hold (unapproved vendor, no PO)
    """
    # Clear existing data in foreign-key dependency order
    db.query(LedgerEntry).delete()
    db.query(Signature).delete()
    db.query(AuditLog).delete()
    db.query(PaymentRequest).delete()
    db.query(GoodsReceipt).delete()
    db.query(PurchaseOrder).delete()
    db.query(Approver).delete()
    db.query(Vendor).delete()
    db.query(PolicyVersion).delete()
    db.commit()

    now = datetime.utcnow()

    # 1. Seed Policy Version 1
    policy_v1 = PolicyVersion(
        version=1,
        policy_json=json.dumps(DEFAULT_POLICY_CONFIG, indent=2),
        created_at=now - timedelta(days=30),
        created_by="system_init",
        active=True,
    )
    db.add(policy_v1)

    # 2. Seed Authorized Approvers (for Separation of Duties)
    approvers = [
        Approver(
            approver_id="APP-001",
            name="Alice Smith",
            role="senior_administrator",
            active=True,
            credential_id="cred_alice_001",
            public_key="MOCK_PK_ALICE_ADMIN_WEBAUTHN",
            sign_count=12,
        ),
        Approver(
            approver_id="APP-002",
            name="Bob Jones",
            role="finance_head",
            active=True,
            credential_id="cred_bob_002",
            public_key="MOCK_PK_BOB_FINANCE_WEBAUTHN",
            sign_count=8,
        ),
        Approver(
            approver_id="APP-003",
            name="Charlie Brown",
            role="senior_executive",
            active=True,
            credential_id="cred_charlie_003",
            public_key="MOCK_PK_CHARLIE_EXEC_WEBAUTHN",
            sign_count=5,
        ),
    ]
    db.add_all(approvers)

    # 3. Seed Simulated Vendors for Acme Ltd
    vendors = [
        Vendor(
            vendor_id="VEND-001",
            vendor_name="Acme Industrial Supplies",
            approved=True,
            bank_account="ACME-BANK-001",
            onboarded_date=now - timedelta(days=180),
            usual_amount_mean=45000.0,
            usual_amount_std=5000.0,
            usual_hour=14.0,
            usual_weekday=2,
        ),
        Vendor(
            vendor_id="VEND-002",
            vendor_name="Global Logistics Corp",
            approved=True,
            bank_account="GLOB-BANK-002",
            onboarded_date=now - timedelta(days=365),
            usual_amount_mean=120000.0,
            usual_amount_std=15000.0,
            usual_hour=11.0,
            usual_weekday=3,
        ),
        Vendor(
            vendor_id="VEND-003",
            vendor_name="Apex Cloud Infrastructure",
            approved=True,
            bank_account="APEX-BANK-003",
            onboarded_date=now - timedelta(days=120),
            usual_amount_mean=50000.0,
            usual_amount_std=5000.0,
            usual_hour=10.0,
            usual_weekday=1,
        ),
        Vendor(
            vendor_id="VEND-004",
            vendor_name="Shadow Shell Enterprises",
            approved=False,
            bank_account="SHAD-BANK-999",
            onboarded_date=now - timedelta(days=1),
            usual_amount_mean=0.0,
            usual_amount_std=0.0,
            usual_hour=3.0,
            usual_weekday=6,
        ),
    ]
    db.add_all(vendors)

    # 4. Seed Purchase Orders
    purchase_orders = [
        PurchaseOrder(
            po_id="PO-2026-001",
            vendor_id="VEND-001",
            amount=45000.0,
            status="APPROVED",
            date=now - timedelta(days=10),
        ),
        PurchaseOrder(
            po_id="PO-2026-002",
            vendor_id="VEND-002",
            amount=150000.0,
            status="APPROVED",
            date=now - timedelta(days=5),
        ),
        PurchaseOrder(
            po_id="PO-2026-003",
            vendor_id="VEND-003",
            amount=50000.0,
            status="APPROVED",
            date=now - timedelta(days=3),
        ),
    ]
    db.add_all(purchase_orders)

    # 5. Seed Goods Receipts (GRNs)
    goods_receipts = [
        GoodsReceipt(
            grn_id="GRN-2026-001",
            po_id="PO-2026-001",
            received=True,
            date=now - timedelta(days=8),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-002",
            po_id="PO-2026-002",
            received=True,
            date=now - timedelta(days=4),
        ),
        GoodsReceipt(
            grn_id="GRN-2026-003",
            po_id="PO-2026-003",
            received=True,
            date=now - timedelta(days=2),
        ),
    ]
    db.add_all(goods_receipts)

    # 6. Seed Demo Payment Requests
    payment_requests = [
        # Scenario 1: Low risk, matching PO/GRN, approved vendor
        PaymentRequest(
            request_id="REQ-DEMO-001",
            vendor_id="VEND-001",
            amount=45000.0,
            currency="INR",
            bank_account="ACME-BANK-001",
            invoice_id="INV-2026-001",
            po_id="PO-2026-001",
            timestamp=now - timedelta(hours=6),
            channel="portal",
            document_quality_score=0.98,
            status="PENDING",
            requester_id="emp_accounts_01",
            processor_id=None,
        ),
        # Scenario 2: Medium risk, larger amount requiring single signature
        PaymentRequest(
            request_id="REQ-DEMO-002",
            vendor_id="VEND-002",
            amount=150000.0,
            currency="INR",
            bank_account="GLOB-BANK-002",
            invoice_id="INV-2026-002",
            po_id="PO-2026-002",
            timestamp=now - timedelta(hours=4),
            channel="portal",
            document_quality_score=0.95,
            status="PENDING",
            requester_id="emp_accounts_02",
            processor_id=None,
        ),
        # Scenario 3: Pre-configured payment for Tamper Demo
        PaymentRequest(
            request_id="REQ-DEMO-003",
            vendor_id="VEND-003",
            amount=50000.0,
            currency="INR",
            bank_account="APEX-BANK-003",
            invoice_id="INV-2026-003",
            po_id="PO-2026-003",
            timestamp=now - timedelta(hours=2),
            channel="portal",
            document_quality_score=0.92,
            status="PENDING",
            requester_id="emp_accounts_01",
            processor_id=None,
        ),
        # Scenario 4: High risk, unapproved vendor, no PO, suspicious channel
        PaymentRequest(
            request_id="REQ-DEMO-004",
            vendor_id="VEND-004",
            amount=500000.0,
            currency="INR",
            bank_account="SHAD-BANK-999",
            invoice_id="INV-2026-999",
            po_id=None,
            timestamp=now - timedelta(hours=1),
            channel="manual_override",
            document_quality_score=0.45,
            status="PENDING",
            requester_id="emp_rogue_99",
            processor_id=None,
        ),
    ]
    db.add_all(payment_requests)
    db.commit()

    # Log seed event in tamper-evident audit log
    log_event(
        db=db,
        user_id="system_seeder",
        action="DATABASE_SEEDED",
        result="SUCCESS",
        details={
            "company": "Acme Ltd",
            "vendors_count": len(vendors),
            "purchase_orders_count": len(purchase_orders),
            "goods_receipts_count": len(goods_receipts),
            "payment_requests_count": len(payment_requests),
            "approvers_count": len(approvers),
            "policy_version": 1,
        },
    )

    return {
        "message": "Demo database successfully seeded for Acme Ltd",
        "company": "Acme Ltd",
        "vendors_count": len(vendors),
        "purchase_orders_count": len(purchase_orders),
        "goods_receipts_count": len(goods_receipts),
        "payment_requests_count": len(payment_requests),
        "approvers_count": len(approvers),
        "policy_version": 1,
        "scenarios": [
            {"id": "REQ-DEMO-001", "description": "Scenario 1: Low risk (auto-approve target)"},
            {"id": "REQ-DEMO-002", "description": "Scenario 2: Medium risk (single signature target)"},
            {"id": "REQ-DEMO-003", "description": "Scenario 3: Tamper demo baseline payment"},
            {"id": "REQ-DEMO-004", "description": "Scenario 4: High risk / hold target (no PO, shadow vendor)"},
        ],
    }
