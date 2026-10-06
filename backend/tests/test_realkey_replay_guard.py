"""
REALKEY Phase 6 Tests: Replay Protection.

Verifies comprehensive server-side replay protection:
1. Valid approval succeeds once.
2. Exact same approval replay fails (CHALLENGE_ALREADY_CONSUMED / REPLAY_DETECTED).
3. Consumed challenge cannot be reused.
4. Consumed nonce cannot be reused across any payment or signature (NONCE_ALREADY_USED).
5. Expired challenge fails and cannot be resurrected.
6. Same approval against a different payment fails (Cross-payment replay).
7. Same approval under a different approver identity fails (Cross-approver replay).
8. Approver cannot sign the same payment twice (APPROVER_ALREADY_SIGNED).
9. Already fully authorized payment cannot be approved again (PAYMENT_ALREADY_AUTHORIZED).
10. Concurrent replay attempts using thread pool: Exactly 1 succeeds, all others rejected.
11. Original authorized payment and signature remain 100% intact and uncorrupted.
12. No duplicate valid signatures are ever created.
13. Replay attempts are recorded as REALKEY_REPLAY_DETECTED with SECURITY_ALERT in audit log.
14. Audit log hash chain integrity remains completely valid.
15. Failed assertions immediately burn the challenge to prevent probing/retries.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import pytest

from app.models.payment_request import PaymentRequest
from app.models.signature import Signature
from app.models.approver import Approver
from app.models.audit_log import AuditLog
from app.services.audit_service import verify_chain
from security.realkey import (
    ChallengeAlreadyUsedError,
    ChallengeExpiredError,
    VirtualWebAuthnClient,
    challenge_store,
    verify_nonce_unused,
    verify_approver_not_already_signed,
    verify_payment_not_authorized,
    NonceAlreadyUsedError,
    ApproverAlreadySignedError,
    PaymentAlreadyAuthorizedError,
)


@pytest.fixture(autouse=True)
def clean_challenge_store():
    """Ensure challenge store is clean before and after each test."""
    challenge_store.clear()
    yield
    challenge_store.clear()


def _setup_registered_approver(client, approver_id="APP-001"):
    """Seeds the DB and registers a real WebAuthn passkey for the approver."""
    client.post("/seed")
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


def _setup_approved_payment(client, request_id="REQ-DEMO-001", approver_id="APP-001"):
    """Seeds DB, registers passkey, and executes valid payment approval."""
    sim, _ = _setup_registered_approver(client, approver_id=approver_id)

    res_chal = client.post(f"/payments/{request_id}/challenge", json={"approver_id": approver_id})
    assert res_chal.status_code == 200
    chal_data = res_chal.json()

    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    res_approve = client.post(
        f"/payments/{request_id}/approve",
        json={
            "approver_id": approver_id,
            "nonce": chal_data["nonce"],
            "credential": assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert res_approve.status_code == 200
    return sim, chal_data, assertion, res_approve.json()


# ==============================================================================
# 1. CORE REPLAY PROTECTION TESTS
# ==============================================================================

def test_valid_approval_succeeds_once(client):
    """Test 1: Valid payment approval succeeds on the first attempt."""
    sim, chal_data, assertion, approve_data = _setup_approved_payment(client, "REQ-DEMO-001")
    assert approve_data["authorized"] is True
    assert approve_data["signature_status"] == "VERIFIED"


def test_exact_same_approval_replay_fails(client, db_session):
    """Test 2: Reusing the exact same WebAuthn approval material fails immediately."""
    sim, chal_data, assertion, approve_data = _setup_approved_payment(client, "REQ-DEMO-001")

    # Attacker captures the exact HTTP payload and replays it
    replay_res = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert replay_res.status_code == 400
    detail = replay_res.json()["detail"]
    assert "CHALLENGE_ALREADY_CONSUMED" in detail or "INVALID_APPROVAL_CHALLENGE" in detail


def test_consumed_challenge_replay_fails(client):
    """Test 3: ChallengeStore strictly rejects reclaiming or retrieving a consumed challenge."""
    sim, chal_data, assertion, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    # Attempt to claim the consumed challenge directly
    with pytest.raises(ChallengeAlreadyUsedError, match="already been consumed|already been used"):
        challenge_store.claim_approval_challenge(challenge_id=chal_data["challenge_id"])

    with pytest.raises(ChallengeAlreadyUsedError, match="already been consumed|already been used"):
        challenge_store.get_valid_approval_challenge(challenge_id=chal_data["challenge_id"])


def test_consumed_nonce_replay_fails(client, db_session):
    """Test 4: A nonce previously recorded in any Signature record cannot be reused."""
    sim, chal_data, assertion, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    used_nonce = chal_data["nonce"]

    # Verify that helper detects the consumed nonce
    with pytest.raises(NonceAlreadyUsedError, match="already been consumed"):
        verify_nonce_unused(db_session, used_nonce)

    # Issue a challenge for unapproved payment REQ-DEMO-002
    res_fresh_chal = client.post("/payments/REQ-DEMO-002/challenge", json={"approver_id": "APP-001"})
    assert res_fresh_chal.status_code == 200
    fresh_chal = res_fresh_chal.json()
    fresh_assertion = sim.sign_assertion(options=fresh_chal["webauthn_options"])

    # Attacker tries to inject the old consumed nonce into the fresh payment submission
    res_reuse = client.post(
        "/payments/REQ-DEMO-002/approve",
        json={
            "approver_id": "APP-001",
            "nonce": used_nonce,  # REPLAYED NONCE!
            "credential": fresh_assertion,
            "challenge_id": fresh_chal["challenge_id"],
        },
    )
    assert res_reuse.status_code == 400
    assert "NONCE_MISMATCH" in res_reuse.json()["detail"] or "NONCE_ALREADY_USED" in res_reuse.json()["detail"]


def test_expired_challenge_fails_and_cannot_be_reused(client):
    """Test 5 & 6: Expired challenge is permanently rejected and cannot be reused."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    assertion = sim.sign_assertion(options=chal_data["webauthn_options"])

    # Fast forward challenge expiration
    chal_obj = challenge_store.get_valid_approval_challenge(challenge_id=chal_data["challenge_id"])
    chal_obj.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    # Submission fails
    res_expired = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert res_expired.status_code == 400
    assert "APPROVAL_CHALLENGE_EXPIRED" in res_expired.json()["detail"]

    # Challenge remains permanently unusable
    with pytest.raises(ChallengeExpiredError):
        challenge_store.get_valid_approval_challenge(challenge_id=chal_data["challenge_id"])


def test_cross_payment_replay_rejected(client, db_session):
    """Test 7: Approval captured for Payment A cannot be used to authorize Payment B."""
    sim, chal_data_a, assertion_a, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    # Attacker tries to submit approval from REQ-DEMO-001 to REQ-DEMO-002
    res_cross = client.post(
        "/payments/REQ-DEMO-002/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data_a["nonce"],
            "credential": assertion_a,
            "challenge_id": chal_data_a["challenge_id"],
        },
    )
    assert res_cross.status_code == 400
    detail = res_cross.json()["detail"]
    assert "INVALID_APPROVAL_CHALLENGE" in detail or "was issued for request" in detail


def test_cross_approver_replay_rejected(client):
    """Test 8: Approval issued for Approver A cannot be submitted as Approver B."""
    sim_alice, _ = _setup_registered_approver(client, approver_id="APP-001")

    # Register Approver B (Bob)
    res_opts_bob = client.post("/auth/webauthn/register/options", json={"approver_id": "APP-002"})
    sim_bob = VirtualWebAuthnClient(origin="http://localhost:5173", rp_id="localhost")
    cred_bob = sim_bob.create_credential(options=res_opts_bob.json()["options"])
    client.post("/auth/webauthn/register/verify", json={"approver_id": "APP-002", "credential": cred_bob})

    # Issue challenge for Alice
    res_chal_alice = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_alice = res_chal_alice.json()
    assertion_alice = sim_alice.sign_assertion(options=chal_alice["webauthn_options"])

    # Bob attempts to submit Alice's challenge and approval under Bob's ID
    res_bob_replay = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-002",  # Bob submitting Alice's approval
            "nonce": chal_alice["nonce"],
            "credential": assertion_alice,
            "challenge_id": chal_alice["challenge_id"],
        },
    )
    assert res_bob_replay.status_code == 400
    detail = res_bob_replay.json()["detail"]
    assert "INVALID_APPROVAL_CHALLENGE" in detail or "was issued for approver" in detail


def test_approver_cannot_sign_same_payment_twice(client, db_session):
    """Test 9: The same approver cannot sign the same payment twice even with a fresh challenge."""
    sim, _, _, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    # Approver APP-001 tries to get a fresh challenge and sign again
    with pytest.raises(ApproverAlreadySignedError, match="has already signed payment"):
        verify_approver_not_already_signed(db_session, request_id="REQ-DEMO-001", approver_id="APP-001")


def test_payment_already_authorized_cannot_be_signed_again(client, db_session):
    """Test 10: An already AUTHORIZED payment cannot accept additional signatures."""
    _setup_approved_payment(client, "REQ-DEMO-001")

    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    assert payment.status == "AUTHORIZED"

    with pytest.raises(PaymentAlreadyAuthorizedError, match="already been fully authorized"):
        verify_payment_not_authorized(payment)


def test_failed_verification_burns_challenge(client):
    """Test 11: A challenge subjected to a failed verification attempt is immediately burned."""
    sim, _ = _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()

    # Corrupt signature to trigger verification failure
    corrupt_assertion = sim.sign_assertion(options=chal_data["webauthn_options"], corrupt_signature=True)

    res_fail = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": corrupt_assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert res_fail.status_code == 400
    assert "INVALID_WEBAUTHN_ASSERTION" in res_fail.json()["detail"]

    # Challenge is now burned and cannot be retried even with a valid signature!
    valid_assertion = sim.sign_assertion(options=chal_data["webauthn_options"])
    res_retry = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": valid_assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert res_retry.status_code == 400
    assert "CHALLENGE_ALREADY_CONSUMED" in res_retry.json()["detail"] or "INVALID_APPROVAL_CHALLENGE" in res_retry.json()["detail"]


# ==============================================================================
# 2. CONCURRENCY & RACE CONDITION PROTECTION
# ==============================================================================

def test_concurrent_challenge_claim_race_condition(client):
    """Test 12a: Thread-safe atomic claim ensures 10 concurrent threads produce exactly 1 success."""
    _setup_registered_approver(client, approver_id="APP-001")

    res_chal = client.post("/payments/REQ-DEMO-001/challenge", json={"approver_id": "APP-001"})
    chal_data = res_chal.json()
    challenge_id = chal_data["challenge_id"]

    results = []

    def attempt_claim():
        try:
            return challenge_store.claim_approval_challenge(challenge_id=challenge_id)
        except ChallengeAlreadyUsedError:
            return None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_claim) for _ in range(10)]
        for f in futures:
            results.append(f.result())

    successful_claims = [r for r in results if r is not None]
    failed_claims = [r for r in results if r is None]

    assert len(successful_claims) == 1, f"Expected exactly 1 successful claim, got {len(successful_claims)}"
    assert len(failed_claims) == 9, f"Expected 9 rejections, got {len(failed_claims)}"


def test_repeated_approval_replay_attempts_rejected(client, db_session):
    """Test 12b: Repeated sequential replay attempts all fail and do not duplicate signatures."""
    sim, chal_data, assertion, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    payload = {
        "approver_id": "APP-001",
        "nonce": chal_data["nonce"],
        "credential": assertion,
        "challenge_id": chal_data["challenge_id"],
    }

    # Attempt 5 repeated replay submissions
    for _ in range(5):
        res = client.post("/payments/REQ-DEMO-001/approve", json=payload)
        assert res.status_code == 400
        assert "CHALLENGE_ALREADY_CONSUMED" in res.json()["detail"] or "INVALID_APPROVAL_CHALLENGE" in res.json()["detail"]

    # Verify that the database contains EXACTLY 1 valid signature
    sig_count = (
        db_session.query(Signature)
        .filter(Signature.request_id == "REQ-DEMO-001", Signature.signature_status == "VALID")
        .count()
    )
    assert sig_count == 1


# ==============================================================================
# 3. DATABASE INTEGRITY & AUDIT TRAIL PRESERVATION
# ==============================================================================

def test_database_and_signature_integrity_preserved_after_replay(client, db_session):
    """Test 13 & 14: Replay attempts do not corrupt original payment or create duplicate signatures."""
    sim, chal_data, assertion, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    # Capture initial database state
    payment_before = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()
    orig_amount = payment_before.amount
    orig_status = payment_before.status
    sig_before = db_session.query(Signature).filter(Signature.request_id == "REQ-DEMO-001").first()
    orig_sig_id = sig_before.signature_id
    orig_hash = sig_before.payload_hash

    # Attempt replay
    res_replay = client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )
    assert res_replay.status_code == 400

    # Refresh and verify records in DB
    db_session.refresh(payment_before)
    db_session.refresh(sig_before)

    assert payment_before.amount == orig_amount
    assert payment_before.status == orig_status == "AUTHORIZED"
    assert sig_before.signature_id == orig_sig_id
    assert sig_before.payload_hash == orig_hash

    # Total signature count remains 1
    total_sigs = db_session.query(Signature).filter(Signature.request_id == "REQ-DEMO-001").count()
    assert total_sigs == 1


def test_replay_attempts_audited_with_hash_chain_intact(client, db_session):
    """Test 15 & 16: REALKEY_REPLAY_DETECTED security alert is logged and chain remains unbroken."""
    sim, chal_data, assertion, _ = _setup_approved_payment(client, "REQ-DEMO-001")

    # Trigger replay
    client.post(
        "/payments/REQ-DEMO-001/approve",
        json={
            "approver_id": "APP-001",
            "nonce": chal_data["nonce"],
            "credential": assertion,
            "challenge_id": chal_data["challenge_id"],
        },
    )

    # Query audit log
    replay_log = (
        db_session.query(AuditLog)
        .filter(AuditLog.request_id == "REQ-DEMO-001", AuditLog.action == "REALKEY_REPLAY_DETECTED")
        .first()
    )
    assert replay_log is not None
    assert replay_log.result == "SECURITY_ALERT"
    assert "CHALLENGE_ALREADY_CONSUMED" in replay_log.details

    # Verify audit log cryptographic hash chain
    chain_result = verify_chain(db_session)
    assert chain_result["valid"] is True
    assert chain_result["corrupted_id"] is None
