"""
REALKEY Phase 7 — Separation of Duties (SoD) Comprehensive Tests.

Tests the fundamental security requirement:
    PREPARER ≠ APPROVER

Test coverage:
1. Different preparer and approver -> approval succeeds.
2. Same preparer and approver -> approval challenge rejected.
3. Self-approval reason is SEPARATION_OF_DUTIES_VIOLATION.
4. Self-approval does not create a valid Signature.
5. Self-approval does not authorize payment.
6. Same identity with both PREPARER and APPROVER roles is still rejected.
7. Different approver can approve the same payment if policy allows.
8. A preparer can approve a different payment.
9. SoD is evaluated per payment (cross-payment isolation).
10. Frontend-supplied preparer ID cannot bypass the backend rule.
11. Direct approval submission with self-approver is rejected and burns challenge.
12. Separation of Duties violation is audit logged with SECURITY_ALERT.
13. Audit hash chain remains cryptographically valid.
14. No private keys or raw credential material are logged.
15. Hackathon demo scenario (Alice prepares, Alice signs -> BLOCKED; Bob signs -> VALID).
16. Tamper detection and replay protection remain functional alongside SoD.
"""

import json
import pytest
from app.models.approver import Approver
from app.models.payment_request import PaymentRequest
from app.models.signature import Signature
from app.models.audit_log import AuditLog
from app.services.audit_service import verify_chain
from security.realkey import challenge_store, VirtualWebAuthnClient


@pytest.fixture(autouse=True)
def clean_challenge_store():
    """Ensure challenge store is clean before and after each test."""
    challenge_store.clear()
    yield
    challenge_store.clear()


def _setup_registered_approver(client, approver_id="APP-001"):
    """Registers a real WebAuthn passkey for the specified approver."""
    res_opts = client.post("/auth/webauthn/register/options", json={"approver_id": approver_id})
    assert res_opts.status_code == 200
    options = res_opts.json()["options"]

    sim = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred = sim.create_credential(options=options)

    res_verify = client.post(
        "/auth/webauthn/register/verify",
        json={"approver_id": approver_id, "credential": cred},
    )
    assert res_verify.status_code == 200
    return sim, cred


def _create_test_payment(client, vendor_id="VEND-001", amount=50000.0, preparer_id="emp_prep_01", invoice_id="INV-SOD-001", po_id="PO-2026-001"):
    """Creates a payment request with an authoritative preparer."""
    res = client.post(
        "/payment-requests",
        json={
            "vendor_id": vendor_id,
            "amount": amount,
            "currency": "INR",
            "bank_account": "ACME-BANK-001",
            "invoice_id": invoice_id,
            "po_id": po_id,
            "channel": "portal",
            "preparer_id": preparer_id,
        },
    )
    assert res.status_code == 201
    return res.json()["request_id"]


def test_different_preparer_and_approver_succeeds(client, db_session):
    """Test 1: When preparer != approver, approval succeeds completely."""
    client.post("/seed")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    # Payment prepared by Alice (APP-001)
    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-DIFF-001")

    # Bob (APP-002) requests challenge
    res_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-002"})
    assert res_chal.status_code == 200
    chal_data = res_chal.json()

    # Bob signs with his passkey
    assertion = sim_bob.sign_assertion(options=chal_data["webauthn_options"])
    res_appr = client.post(
        f"/payments/{req_id}/approve",
        json={
            "approver_id": "APP-002",
            "nonce": chal_data["nonce"],
            "credential": assertion,
        },
    )
    assert res_appr.status_code == 200
    data = res_appr.json()
    assert data["authorized"] is True
    assert data["signature_status"] == "VERIFIED"
    assert data["approver_id"] == "APP-002"

    # Database verification
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == req_id).first()
    assert payment.status == "AUTHORIZED"
    sig = db_session.query(Signature).filter(Signature.request_id == req_id).first()
    assert sig is not None
    assert sig.approver_id == "APP-002"


def test_same_preparer_and_approver_challenge_rejected(client, db_session):
    """Test 2 & 3: When preparer == approver, challenge creation is immediately rejected."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    # Payment prepared by Alice (APP-001)
    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-SELF-001")

    # Alice attempts to request challenge to approve her own payment
    res_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 400
    detail = res_chal.json()["detail"]
    assert "SEPARATION_OF_DUTIES_VIOLATION" in detail

    # Confirm no challenge exists in store
    assert len(challenge_store._approval_challenges_by_id) == 0


def test_self_approval_does_not_create_signature_or_authorize(client, db_session):
    """Test 4 & 5: Self-approval attempt persists NO signature and leaves payment unauthorized."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-SELF-002")

    # Attempt challenge -> rejected
    res_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 400

    # Verify database integrity
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == req_id).first()
    assert payment.status == "PENDING"
    assert payment.status != "AUTHORIZED"

    sigs_count = db_session.query(Signature).filter(Signature.request_id == req_id).count()
    assert sigs_count == 0


def test_same_identity_with_different_roles_rejected(client, db_session):
    """Test 6: User with dual roles (PREPARER and APPROVER) is still rejected; identity matters."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    # Update Alice's role to reflect dual roles
    alice = db_session.query(Approver).filter(Approver.approver_id == "APP-001").first()
    alice.role = "preparer,senior_administrator"
    db_session.commit()

    # Alice prepares payment
    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-DUAL-001")

    # Alice attempts to approve her own payment
    res_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_chal.json()["detail"]


def test_different_approver_can_approve_payment(client, db_session):
    """Test 7: Different registered approver can approve the payment."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-DIFF-002")

    # Alice cannot approve
    res_alice = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_alice.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_alice.json()["detail"]

    # Bob can approve
    res_bob = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-002"})
    assert res_bob.status_code == 200
    bob_chal = res_bob.json()

    assertion = sim_bob.sign_assertion(options=bob_chal["webauthn_options"])
    res_appr = client.post(
        f"/payments/{req_id}/approve",
        json={"approver_id": "APP-002", "nonce": bob_chal["nonce"], "credential": assertion},
    )
    assert res_appr.status_code == 200
    assert res_appr.json()["authorized"] is True


def test_preparer_can_approve_different_payment(client, db_session):
    """Test 8 & 9: SoD is evaluated per payment. Alice prepares Payment A, but can approve Payment B."""
    client.post("/seed")
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    # Payment A prepared by Alice (APP-001)
    req_a = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-PAY-A")
    # Payment B prepared by Bob (APP-002)
    req_b = _create_test_payment(client, preparer_id="APP-002", invoice_id="INV-PAY-B")

    # Alice CANNOT approve Payment A
    res_a = client.post(f"/payments/{req_a}/challenge", json={"approver_id": "APP-001"})
    assert res_a.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_a.json()["detail"]

    # Alice CAN approve Payment B
    res_b = client.post(f"/payments/{req_b}/challenge", json={"approver_id": "APP-001"})
    assert res_b.status_code == 200
    chal_b = res_b.json()

    assertion = sim_alice.sign_assertion(options=chal_b["webauthn_options"])
    res_appr_b = client.post(
        f"/payments/{req_b}/approve",
        json={"approver_id": "APP-001", "nonce": chal_b["nonce"], "credential": assertion},
    )
    assert res_appr_b.status_code == 200
    assert res_appr_b.json()["authorized"] is True


def test_cross_payment_isolation_two_way(client, db_session):
    """Test 9: Mutual cross-approval between two preparers works correctly."""
    client.post("/seed")
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    req_a = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-MUT-A")
    req_b = _create_test_payment(client, preparer_id="APP-002", invoice_id="INV-MUT-B")

    # Bob approves Alice's payment (Payment A)
    chal_a = client.post(f"/payments/{req_a}/challenge", json={"approver_id": "APP-002"}).json()
    assert_a = sim_bob.sign_assertion(options=chal_a["webauthn_options"])
    appr_a = client.post(
        f"/payments/{req_a}/approve",
        json={"approver_id": "APP-002", "nonce": chal_a["nonce"], "credential": assert_a},
    )
    assert appr_a.status_code == 200
    assert appr_a.json()["authorized"] is True

    # Alice approves Bob's payment (Payment B)
    chal_b = client.post(f"/payments/{req_b}/challenge", json={"approver_id": "APP-001"}).json()
    assert_b = sim_alice.sign_assertion(options=chal_b["webauthn_options"])
    appr_b = client.post(
        f"/payments/{req_b}/approve",
        json={"approver_id": "APP-001", "nonce": chal_b["nonce"], "credential": assert_b},
    )
    assert appr_b.status_code == 200
    assert appr_b.json()["authorized"] is True


def test_frontend_supplied_preparer_id_cannot_bypass_rule(client, db_session):
    """Test 10: Frontend attempt to falsify preparer_id in challenge body is ignored."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    # Payment prepared by Alice (APP-001)
    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-FORGE-001")

    # Alice requests challenge but claims someone else prepared it in the JSON body
    res_chal = client.post(
        f"/payments/{req_id}/challenge",
        json={"approver_id": "APP-001", "preparer_id": "someone_else_emp_999"},
    )
    # The server strictly reads payment.requester_id from the DB and rejects!
    assert res_chal.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_chal.json()["detail"]


def test_direct_approval_submission_self_approver_rejected(client, db_session):
    """Test 11: Even if an attacker directly hits /approve without a challenge, SoD blocks it."""
    client.post("/seed")
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")

    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-DIRECT-001")

    res_appr = client.post(
        f"/payments/{req_id}/approve",
        json={
            "approver_id": "APP-001",
            "nonce": "fake-nonce",
            "challenge_id": "fake-challenge",
            "signature": "fake-sig",
            "authenticator_data": "fake-auth",
            "client_data_json": "fake-client",
        },
    )
    assert res_appr.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_appr.json()["detail"]

    # Verify no signature was created
    assert db_session.query(Signature).filter(Signature.request_id == req_id).count() == 0


def test_sod_violation_audit_logged_with_hash_chain_intact(client, db_session):
    """Test 12, 13, 14: SoD violation writes a SECURITY_ALERT audit log and chain remains valid."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-AUDIT-001")

    # Trigger SoD violation
    client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})

    # Check audit log
    latest_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "SEPARATION_OF_DUTIES_VIOLATION")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    assert latest_log is not None
    assert latest_log.result == "SECURITY_ALERT"
    assert latest_log.request_id == req_id
    assert latest_log.user_id == "APP-001"

    # Verify no private key or credential leaked into details
    details = json.loads(latest_log.details)
    assert details["reason"] == "SEPARATION_OF_DUTIES_VIOLATION"
    assert "private_key" not in details
    assert "credential" not in details
    assert "signature" not in details

    # Verify cryptographic audit hash chain integrity
    chain_status = verify_chain(db_session)
    assert chain_status["valid"] is True
    assert chain_status["corrupted_id"] is None


def test_hackathon_demo_scenario_alice_bob(client, db_session):
    """
    Test 15: Hackathon Demo Scenario.
    --------------------------------------------
    PAYMENT PREPARER: Alice (APP-001)
    PAYMENT: ABC Suppliers (VEND-001), ₹50,000

    APPROVAL ATTEMPT: Alice signs with passkey
    RESULT: ❌ APPROVAL BLOCKED: SEPARATION_OF_DUTIES_VIOLATION
    --------------------------------------------
    APPROVER: Bob (APP-002)
    Bob signs with passkey
    RESULT: ✅ VALID REALKEY APPROVAL
    --------------------------------------------
    """
    client.post("/seed")
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    # Step 1: Alice prepares payment
    req_id = _create_test_payment(
        client,
        vendor_id="VEND-001",
        amount=50000.0,
        preparer_id="APP-001",
        invoice_id="INV-HACK-001",
    )

    # Step 2: Alice attempts self-approval
    res_alice_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_alice_chal.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_alice_chal.json()["detail"]

    # Verify payment is NOT authorized and has NO signatures
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == req_id).first()
    assert payment.status == "PENDING"
    assert db_session.query(Signature).filter(Signature.request_id == req_id).count() == 0

    # Step 3: Independent approver Bob signs
    res_bob_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-002"})
    assert res_bob_chal.status_code == 200
    bob_chal_data = res_bob_chal.json()

    bob_assertion = sim_bob.sign_assertion(options=bob_chal_data["webauthn_options"])
    res_bob_appr = client.post(
        f"/payments/{req_id}/approve",
        json={
            "approver_id": "APP-002",
            "nonce": bob_chal_data["nonce"],
            "credential": bob_assertion,
        },
    )
    assert res_bob_appr.status_code == 200
    appr_data = res_bob_appr.json()
    assert appr_data["authorized"] is True
    assert appr_data["signature_status"] == "VERIFIED"
    assert appr_data["approver_id"] == "APP-002"

    # Step 4: Verify payment is now AUTHORIZED with Bob's signature
    db_session.refresh(payment)
    assert payment.status == "AUTHORIZED"
    sigs = db_session.query(Signature).filter(Signature.request_id == req_id).all()
    assert len(sigs) == 1
    assert sigs[0].approver_id == "APP-002"


def test_tamper_detection_and_replay_protection_remain_functional_with_sod(client, db_session):
    """Test 16: Tamper detection and replay protection remain 100% functional with SoD active."""
    client.post("/seed")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    # Alice prepares payment
    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-TAMPER-SOD-001")

    # Bob signs payment
    chal_data = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-002"}).json()
    assertion = sim_bob.sign_assertion(options=chal_data["webauthn_options"])
    approve_payload = {
        "approver_id": "APP-002",
        "nonce": chal_data["nonce"],
        "credential": assertion,
    }
    res_appr = client.post(f"/payments/{req_id}/approve", json=approve_payload)
    assert res_appr.status_code == 200

    # 1. Replay Guard check: Replaying the exact same approval fails
    res_replay = client.post(f"/payments/{req_id}/approve", json=approve_payload)
    assert res_replay.status_code == 400

    # 2. Tamper Demo check: Tampering with amount detects alteration
    res_tamper = client.post(
        f"/payments/{req_id}/tamper-demo",
        json={"field": "amount", "tampered_value": 500000.0},
    )
    assert res_tamper.status_code == 200
    tamper_result = res_tamper.json()
    assert tamper_result["tamper_detected"] is True
    assert tamper_result["approval_valid"] is False
    assert tamper_result["reason"] == "PAYMENT_HASH_MISMATCH"


def test_cross_payment_replay_remains_rejected_with_sod(client, db_session):
    """Test 17: Assertion approved for Payment A cannot be replayed on Payment B."""
    client.post("/seed")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")

    req_a = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-XREPLAY-A")
    req_b = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-XREPLAY-B")

    # Bob requests challenge and signs for Payment A
    chal_a = client.post(f"/payments/{req_a}/challenge", json={"approver_id": "APP-002"}).json()
    assert_a = sim_bob.sign_assertion(options=chal_a["webauthn_options"])

    # Attempt to submit Payment A's assertion to Payment B
    res_x = client.post(
        f"/payments/{req_b}/approve",
        json={
            "approver_id": "APP-002",
            "nonce": chal_a["nonce"],
            "credential": assert_a,
            "challenge_id": chal_a["challenge_id"],
        },
    )
    assert res_x.status_code == 400
    assert "CROSS_PAYMENT_REPLAY_DETECTED" in res_x.json()["detail"] or "INVALID_APPROVAL_CHALLENGE" in res_x.json()["detail"]


def test_cross_approver_replay_remains_rejected_with_sod(client, db_session):
    """Test 18: Assertion issued to Approver B cannot be submitted under Approver C."""
    client.post("/seed")
    sim_bob, _ = _setup_registered_approver(client, approver_id="APP-002")
    _setup_registered_approver(client, approver_id="APP-003")

    req_id = _create_test_payment(client, preparer_id="APP-001", invoice_id="INV-XAPPROVER-001")

    chal_bob = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-002"}).json()
    assert_bob = sim_bob.sign_assertion(options=chal_bob["webauthn_options"])

    # Submit Bob's assertion under Charlie's approver ID (APP-003)
    res_x = client.post(
        f"/payments/{req_id}/approve",
        json={
            "approver_id": "APP-003",
            "nonce": chal_bob["nonce"],
            "credential": assert_bob,
            "challenge_id": chal_bob["challenge_id"],
        },
    )
    assert res_x.status_code == 400
    assert "CROSS_APPROVER_REPLAY_DETECTED" in res_x.json()["detail"] or "INVALID_APPROVAL_CHALLENGE" in res_x.json()["detail"]


def test_case_insensitive_and_whitespace_preparer_matching(client, db_session):
    """Test 19: SoD matching is normalized: 'app-001 ' matches 'APP-001'."""
    client.post("/seed")
    _setup_registered_approver(client, approver_id="APP-001")

    # Payment prepared with lowercase and spaces: ' app-001 '
    req_id = _create_test_payment(client, preparer_id=" app-001 ", invoice_id="INV-CASE-001")

    # Attempt approval with 'APP-001'
    res_chal = client.post(f"/payments/{req_id}/challenge", json={"approver_id": "APP-001"})
    assert res_chal.status_code == 400
    assert "SEPARATION_OF_DUTIES_VIOLATION" in res_chal.json()["detail"]

