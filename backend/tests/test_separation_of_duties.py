from datetime import datetime, timedelta
import pytest
from app.models.payment_request import PaymentRequest
from app.models.approver import Approver
from app.models.signature import Signature
from app.services.signature_service import ACTIVE_CHALLENGES


def test_get_signing_challenge_structure(client):
    """Verify GET /payments/{id}/challenge generates exact payment bundle, nonce, and authorized roles."""
    client.post("/seed")
    # Score REQ-DEMO-002 so it transitions to ONE_SIGNATURE (PENDING_APPROVAL)
    score_res = client.post("/payments/REQ-DEMO-002/score")
    assert score_res.status_code == 200

    chal_res = client.get("/payments/REQ-DEMO-002/challenge")
    assert chal_res.status_code == 200
    data = chal_res.json()

    assert data["request_id"] == "REQ-DEMO-002"
    assert data["nonce"].startswith("NONCE-")
    assert data["routing_tier"] == "ONE_SIGNATURE"
    assert data["required_signatures"] == 1
    assert "senior_administrator" in data["authorized_roles"]

    # Verify exact payment bundle
    bundle = data["payment_bundle"]
    assert bundle["request_id"] == "REQ-DEMO-002"
    assert bundle["vendor_id"] == "VEND-002"
    assert bundle["amount"] == 150000.0
    assert bundle["currency"] == "INR"
    assert bundle["beneficiary_bank_account"] == "GLOB-BANK-002"
    assert bundle["nonce"] == data["nonce"]


def test_successful_single_signature_authorization(client):
    """Verify authorized approver signing a ONE_SIGNATURE payment transitions it to AUTHORIZED."""
    client.post("/seed")
    client.post("/payments/REQ-DEMO-002/score")

    # Get challenge
    challenge = client.get("/payments/REQ-DEMO-002/challenge").json()

    # APP-001 is Alice Smith (role: senior_administrator)
    sign_payload = {
        "approver_id": "APP-001",
        "nonce": challenge["nonce"],
        "signature": "VALID_WEBAUTHN_SIG_ALICE_ADMIN_001",
    }
    response = client.post("/payments/REQ-DEMO-002/sign", json=sign_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["payment_status"] == "AUTHORIZED"
    assert data["signature_status"] == "VALID"
    assert data["distinct_signatures_count"] == 1

    # Verify persisted in database
    get_res = client.get("/payments/REQ-DEMO-002")
    assert get_res.json()["status"] == "AUTHORIZED"


def test_separation_of_duties_requester_cannot_approve(client, db_session):
    """Verify rule: Whoever requested a payment cannot approve it (Fail Closed 403)."""
    client.post("/seed")

    # Create payment where requester_id is set to APP-001 (Alice)
    payment = PaymentRequest(
        request_id="REQ-SOD-REQUESTER",
        vendor_id="VEND-002",
        amount=150000.0,
        currency="INR",
        bank_account="GLOB-BANK-002",
        invoice_id="INV-SOD-001",
        po_id="PO-2026-002",
        status="PENDING_APPROVAL",
        routing_tier="ONE_SIGNATURE",
        required_signatures=1,
        requester_id="APP-001",  # Alice requested this payment!
    )
    db_session.add(payment)
    db_session.commit()

    challenge = client.get("/payments/REQ-SOD-REQUESTER/challenge").json()

    # Alice (APP-001) tries to approve her own requested payment
    sign_payload = {
        "approver_id": "APP-001",
        "nonce": challenge["nonce"],
        "signature": "VALID_SIG",
    }
    response = client.post("/payments/REQ-SOD-REQUESTER/sign", json=sign_payload)
    assert response.status_code == 403
    assert "requested the payment cannot approve" in response.json()["detail"].lower()


def test_two_signatures_distinct_approvers_required(client, db_session):
    """Verify rule: Two-signature payments require two distinct approvers. One signature cannot release it."""
    client.post("/seed")

    # Create payment requiring TWO_SIGNATURES (roles: finance_head, senior_executive)
    payment = PaymentRequest(
        request_id="REQ-TWO-SIGS",
        vendor_id="VEND-002",
        amount=250000.0,
        currency="INR",
        bank_account="GLOB-BANK-002",
        invoice_id="INV-TWO-SIGS-01",
        po_id="PO-2026-002",
        status="PENDING_APPROVAL",
        routing_tier="TWO_SIGNATURES",
        required_signatures=2,
    )
    db_session.add(payment)
    db_session.commit()

    # First Signature: APP-002 (Bob Jones, finance_head)
    chal_1 = client.get("/payments/REQ-TWO-SIGS/challenge").json()
    res_1 = client.post(
        "/payments/REQ-TWO-SIGS/sign",
        json={
            "approver_id": "APP-002",
            "nonce": chal_1["nonce"],
            "signature": "VALID_SIG_BOB",
        },
    )
    assert res_1.status_code == 200
    # Crucial: 1 signature MUST NOT release a 2-signature payment
    assert res_1.json()["payment_status"] == "PENDING_APPROVAL"
    assert res_1.json()["distinct_signatures_count"] == 1

    # Bob (APP-002) tries to sign a SECOND time -> Must fail 409 Conflict
    chal_2 = client.get("/payments/REQ-TWO-SIGS/challenge").json()
    dup_res = client.post(
        "/payments/REQ-TWO-SIGS/sign",
        json={
            "approver_id": "APP-002",
            "nonce": chal_2["nonce"],
            "signature": "VALID_SIG_BOB_AGAIN",
        },
    )
    assert dup_res.status_code == 409
    assert "already signed" in dup_res.json()["detail"].lower()

    # Second Signature: Distinct approver APP-003 (Charlie Brown, senior_executive)
    res_2 = client.post(
        "/payments/REQ-TWO-SIGS/sign",
        json={
            "approver_id": "APP-003",
            "nonce": chal_2["nonce"],
            "signature": "VALID_SIG_CHARLIE",
        },
    )
    assert res_2.status_code == 200
    assert res_2.json()["payment_status"] == "AUTHORIZED"
    assert res_2.json()["distinct_signatures_count"] == 2


def test_unauthorized_role_rejected(client, db_session):
    """Verify approver with unauthorized role cannot sign (e.g. senior_administrator trying to sign TWO_SIGNATURES)."""
    client.post("/seed")

    payment = PaymentRequest(
        request_id="REQ-ROLE-TEST",
        vendor_id="VEND-002",
        amount=250000.0,
        currency="INR",
        bank_account="GLOB-BANK-002",
        invoice_id="INV-ROLE-01",
        status="PENDING_APPROVAL",
        routing_tier="TWO_SIGNATURES",  # Requires finance_head, senior_executive
        required_signatures=2,
    )
    db_session.add(payment)
    db_session.commit()

    chal = client.get("/payments/REQ-ROLE-TEST/challenge").json()

    # APP-001 (Alice) is senior_administrator, which is NOT in TWO_SIGNATURES roles
    sign_payload = {
        "approver_id": "APP-001",
        "nonce": chal["nonce"],
        "signature": "SIG_ALICE",
    }
    response = client.post("/payments/REQ-ROLE-TEST/sign", json=sign_payload)
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


def test_nonce_replay_prevention(client):
    """Verify consuming the same nonce twice fails with 400."""
    client.post("/seed")
    client.post("/payments/REQ-DEMO-002/score")

    chal = client.get("/payments/REQ-DEMO-002/challenge").json()

    # First consumption
    sign_1 = client.post(
        "/payments/REQ-DEMO-002/sign",
        json={
            "approver_id": "APP-001",
            "nonce": chal["nonce"],
            "signature": "SIG_VALID_1",
        },
    )
    assert sign_1.status_code == 200

    # Replay attempt
    sign_2 = client.post(
        "/payments/REQ-DEMO-002/sign",
        json={
            "approver_id": "APP-001",
            "nonce": chal["nonce"],
            "signature": "SIG_VALID_REPLAY",
        },
    )
    assert sign_2.status_code in (400, 409)


def test_bundle_tamper_detection(client, db_session):
    """Verify altering payment amount after challenge is generated triggers TAMPER DETECTED."""
    client.post("/seed")
    client.post("/payments/REQ-DEMO-002/score")

    chal = client.get("/payments/REQ-DEMO-002/challenge").json()

    # Tamper: Intentionally change payment amount in DB behind the scenes (e.g. from 150,000 to 1,500,000)
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-002").first()
    payment.amount = 1500000.0
    db_session.commit()

    # Submit signature on original challenge
    sign_payload = {
        "approver_id": "APP-001",
        "nonce": chal["nonce"],
        "signature": "SIG_ORIGINAL",
    }
    response = client.post("/payments/REQ-DEMO-002/sign", json=sign_payload)
    assert response.status_code == 400
    assert "tamper detected" in response.json()["detail"].lower()

    # Verify payment status is set to TAMPER_REJECTED
    payment_after = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-002").first()
    assert payment_after.status == "TAMPER_REJECTED"


def test_invalid_signature_rejected(client):
    """Verify empty or corrupted signature fails closed."""
    client.post("/seed")
    client.post("/payments/REQ-DEMO-002/score")

    chal = client.get("/payments/REQ-DEMO-002/challenge").json()

    sign_payload = {
        "approver_id": "APP-001",
        "nonce": chal["nonce"],
        "signature": "INVALID",
    }
    response = client.post("/payments/REQ-DEMO-002/sign", json=sign_payload)
    assert response.status_code == 401
    assert "signature verification failed" in response.json()["detail"].lower()


def test_webauthn_registration_flow(client):
    """Verify WebAuthn registration begin and finish endpoints."""
    client.post("/seed")

    # 1. Begin registration for APP-001
    begin_res = client.post("/webauthn/register/begin", json={"approver_id": "APP-001"})
    assert begin_res.status_code == 200
    begin_data = begin_res.json()
    assert "challenge" in begin_data
    assert begin_data["user"]["id"] == "APP-001"

    # 2. Finish registration
    finish_res = client.post(
        "/webauthn/register/finish",
        json={
            "approver_id": "APP-001",
            "credential_id": "NEW_CRED_ID_ALICE_999",
            "public_key": "NEW_MOCK_PUBLIC_KEY_BASE64",
        },
    )
    assert finish_res.status_code == 200
    assert finish_res.json()["success"] is True
    assert finish_res.json()["credential_id"] == "NEW_CRED_ID_ALICE_999"
