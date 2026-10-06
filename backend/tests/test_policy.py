from datetime import datetime, timedelta
import pytest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.models.payment_request import PaymentRequest
from app.services.policy_engine import (
    get_active_policy,
    evaluate_routing,
    update_policy_version,
)
from app.schemas.policy import (
    PolicyConfig,
    PolicyThresholds,
    PolicyUpdateRequest,
)


def test_get_policy_endpoint(client):
    """Verify GET /policy returns active policy configuration with version details."""
    client.post("/seed")
    response = client.get("/policy")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] >= 1
    assert data["active"] is True
    assert data["policy"]["auto_approve_cap_amount"] == 50000.0
    assert data["policy"]["thresholds"]["auto_approve_below"] == 30.0
    assert data["policy"]["thresholds"]["one_signature_below"] == 70.0
    assert data["policy"]["thresholds"]["two_signature_below"] == 90.0


def test_update_policy_versioning(client):
    """Verify PUT /policy creates a new policy version, deactivates old version, and updates thresholds."""
    client.post("/seed")

    # Fetch initial version
    initial_res = client.get("/policy")
    initial_ver = initial_res.json()["version"]

    payload = {
        "policy": {
            "version": initial_ver,
            "thresholds": {
                "auto_approve_below": 25.0,
                "one_signature_below": 65.0,
                "two_signature_below": 85.0,
            },
            "auto_approve_cap_amount": 40000.0,
            "monthly_auto_approved_cap_per_vendor": 150000.0,
            "signers": {
                "one_signature": ["senior_administrator"],
                "two_signatures": ["finance_head", "senior_executive"],
            },
            "always_escalate": ["new_vendor", "bank_detail_change"],
            "po_match_tolerance_percent": 1.5,
            "hold_time_limit_hours": 24,
            "windowed_total_days": 7,
        },
        "changed_by": "admin_alice_01",
        "change_reason": "Quarterly risk tolerance tightening",
    }
    response = client.put("/policy", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["version"] == initial_ver + 1
    assert updated["active"] is True
    assert updated["policy"]["auto_approve_cap_amount"] == 40000.0
    assert updated["policy"]["thresholds"]["auto_approve_below"] == 25.0

    # Verify history returns both versions
    history_res = client.get("/policy/history")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) >= 2
    assert history[0]["version"] == initial_ver + 1
    assert history[0]["active"] is True
    assert history[1]["active"] is False


def test_update_policy_invalid_thresholds(client):
    """Verify threshold ordering validation fails when auto_approve_below >= one_signature_below."""
    client.post("/seed")
    payload = {
        "policy": {
            "version": 1,
            "thresholds": {
                "auto_approve_below": 75.0,
                "one_signature_below": 50.0,  # Invalid: less than auto_approve
                "two_signature_below": 90.0,
            },
            "auto_approve_cap_amount": 50000.0,
            "monthly_auto_approved_cap_per_vendor": 200000.0,
            "signers": {
                "one_signature": ["senior_administrator"],
                "two_signatures": ["finance_head", "senior_executive"],
            },
            "always_escalate": [],
            "po_match_tolerance_percent": 2.0,
            "hold_time_limit_hours": 48,
            "windowed_total_days": 7,
        },
        "changed_by": "admin_alice_01",
    }
    response = client.put("/policy", json=payload)
    assert response.status_code == 400
    assert "threshold validation failed" in response.json()["detail"].lower()


def test_low_risk_auto_approval_routing(db_session, client):
    """Verify risk_score < 30 with all valid safety checks routes to AUTO_APPROVE (status: AUTHORIZED)."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=18.0)
    assert routing.routing_tier == "AUTO_APPROVE"
    assert routing.required_signatures == 0
    assert routing.status == "AUTHORIZED"
    assert len(routing.escalation_reasons) == 0


def test_medium_risk_one_signature_routing(db_session, client):
    """Verify 30 <= risk_score < 70 routes to ONE_SIGNATURE (status: PENDING_APPROVAL, req_sigs: 1)."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-002").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=55.0)
    assert routing.routing_tier == "ONE_SIGNATURE"
    assert routing.required_signatures == 1
    assert routing.status == "PENDING_APPROVAL"
    assert "senior_administrator" in routing.authorized_roles


def test_high_risk_two_signatures_routing(db_session, client):
    """Verify 70 <= risk_score < 90 routes to TWO_SIGNATURES (status: PENDING_APPROVAL, req_sigs: 2)."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-002").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=78.0)
    assert routing.routing_tier == "TWO_SIGNATURES"
    assert routing.required_signatures == 2
    assert routing.status == "PENDING_APPROVAL"
    assert "finance_head" in routing.authorized_roles
    assert "senior_executive" in routing.authorized_roles


def test_hold_routing(db_session, client):
    """Verify risk_score >= 90 routes to HOLD (status: ON_HOLD)."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-004").first()

    three_way_facts = {
        "po_exists": 0,
        "po_approved": 0,
        "grn_exists": 0,
        "vendor_approved": 0,
        "amount_match": False,
        "duplicate_invoice": 0,
        "bank_account_changed": 1,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=94.0)
    assert routing.routing_tier == "HOLD"
    assert routing.status == "ON_HOLD"
    assert routing.required_signatures == 0


def test_auto_approval_cap_safeguard(db_session, client):
    """Verify low risk score is escalated to ONE_SIGNATURE if amount exceeds auto-approval cap (50k)."""
    client.post("/seed")
    # VEND-001 payment with low score but amount 75,000 (> 50,000 cap)
    large_payment = PaymentRequest(
        request_id="REQ-LARGE-LOWRISK",
        vendor_id="VEND-001",
        amount=75000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-LARGE-01",
        po_id="PO-2026-001",
        timestamp=datetime.utcnow(),
    )
    db_session.add(large_payment)
    db_session.commit()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, large_payment, three_way_facts, risk_score=15.0)
    assert routing.routing_tier == "ONE_SIGNATURE"
    assert routing.required_signatures == 1
    assert any("exceeds auto-approval cap" in r for r in routing.escalation_reasons)


def test_monthly_vendor_cap_safeguard(db_session, client):
    """Verify low risk score is escalated if 30-day cumulative auto-approvals exceed vendor cap (200k)."""
    client.post("/seed")
    now = datetime.utcnow()

    # Create past auto-approved payments totaling 180,000 for VEND-001
    past_payment = PaymentRequest(
        request_id="REQ-PAST-AUTO-01",
        vendor_id="VEND-001",
        amount=180000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-PAST-01",
        timestamp=now - timedelta(days=5),
        routing_tier="AUTO_APPROVE",
        status="AUTHORIZED",
    )
    # Current payment is 35,000 (180,000 + 35,000 = 215,000 > 200,000 monthly cap)
    current_payment = PaymentRequest(
        request_id="REQ-CURRENT-AUTO-02",
        vendor_id="VEND-001",
        amount=35000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-CURR-02",
        timestamp=now,
    )
    db_session.add_all([past_payment, current_payment])
    db_session.commit()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, current_payment, three_way_facts, risk_score=12.0)
    assert routing.routing_tier == "ONE_SIGNATURE"
    assert any("monthly auto-approved volume" in r for r in routing.escalation_reasons)


def test_new_vendor_always_escalate(db_session, client):
    """Verify new vendor (< 30 days) cannot be auto-approved even with low ML risk score."""
    client.post("/seed")

    # Create a newly onboarded vendor (5 days ago)
    new_vendor = Vendor(
        vendor_id="VEND-BRAND-NEW",
        vendor_name="Brand New Logistics",
        approved=True,
        bank_account="NEW-BANK-100",
        onboarded_date=datetime.utcnow() - timedelta(days=5),
        usual_amount_mean=30000.0,
    )
    payment = PaymentRequest(
        request_id="REQ-NEW-VEND-TEST",
        vendor_id="VEND-BRAND-NEW",
        amount=25000.0,
        currency="INR",
        bank_account="NEW-BANK-100",
        invoice_id="INV-NEW-VEND-01",
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([new_vendor, payment])
    db_session.commit()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=10.0)
    assert routing.routing_tier == "ONE_SIGNATURE"
    assert any("new vendor cannot be auto-approved" in r.lower() for r in routing.escalation_reasons)


def test_bank_detail_change_always_escalate(db_session, client):
    """Verify bank account change triggers mandatory escalation to TWO_SIGNATURES."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 1,  # Bank account was altered!
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=15.0)
    assert routing.routing_tier == "TWO_SIGNATURES"
    assert routing.required_signatures == 2
    assert any("bank account changed" in r.lower() for r in routing.escalation_reasons)


def test_unapproved_vendor_immediately_held(db_session, client):
    """Verify unapproved vendor is unconditionally routed to HOLD regardless of ML score."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 0,  # Unapproved!
        "amount_match": True,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=5.0)
    assert routing.routing_tier == "HOLD"
    assert routing.status == "ON_HOLD"


def test_duplicate_invoice_immediately_held(db_session, client):
    """Verify duplicate invoice detection immediately routes payment to HOLD."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    three_way_facts = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "amount_match": True,
        "duplicate_invoice": 1,  # Duplicate!
        "bank_account_changed": 0,
    }
    routing = evaluate_routing(db_session, payment, three_way_facts, risk_score=10.0)
    assert routing.routing_tier == "HOLD"
    assert routing.status == "ON_HOLD"


def test_scoring_api_with_policy_routing(client):
    """Verify POST /payments/{id}/score returns complete routing result and updates payment status."""
    client.post("/seed")

    # Score low-risk demo payment (REQ-DEMO-001: 45,000, valid PO, valid GRN, known vendor)
    response = client.post("/payments/REQ-DEMO-001/score")
    assert response.status_code == 200
    data = response.json()

    assert "routing" in data
    assert data["routing"]["routing_tier"] == "AUTO_APPROVE"
    assert data["routing"]["required_signatures"] == 0
    assert data["routing"]["status"] == "AUTHORIZED"
    assert data["payment_status"] == "AUTHORIZED"
