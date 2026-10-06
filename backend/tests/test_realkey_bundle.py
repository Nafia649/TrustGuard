"""
REALKEY Phase 3 Unit Tests: Exact Payment Bundle & Canonical Hashing.

Validates:
1. RFC 8785 / JCS compliant canonical serialization.
2. SHA-256 cryptographic digest calculation.
3. Cryptographic sensitivity of each of the 11 security-critical fields.
4. Determinism regardless of dictionary key insertion order.
5. Determinism across numeric representations (50000 vs 50000.0).
6. Nonce unpredictability and uniqueness.
7. Expiry calculation, expiration detection, and rejection.
8. Rejection of missing, extra, or invalid fields.
9. Protection of policy_version and routing_tier from client tampering.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import json
import pytest

from app.models.payment_request import PaymentRequest
from security.realkey.bundle import (
    REQUIRED_PAYMENT_BUNDLE_FIELDS,
    PaymentBundleError,
    PaymentBundleExpiredError,
    PaymentBundleValidationError,
    calculate_bundle_expiry,
    canonicalize_payment_bundle,
    create_payment_bundle,
    create_payment_bundle_from_model,
    format_utc_timestamp,
    generate_payment_nonce,
    hash_payment_bundle,
    is_bundle_expired,
    parse_utc_timestamp,
    validate_payment_bundle,
    verify_bundle_not_expired,
)


@pytest.fixture
def baseline_bundle_data():
    """Provides a consistent baseline 11-field payment bundle."""
    return {
        "vendor_id": "VEND-001",
        "amount": 50000,
        "currency": "INR",
        "bank_account": "ACME-BANK-001",
        "invoice_id": "INV-2026-001",
        "po_id": "PO-2026-001",
        "timestamp": "2026-10-06T12:00:00Z",
        "nonce": "4f7e2d9a1c8b3e5f6a0b1c2d3e4f5a6b",
        "expiry": "2026-10-06T12:05:00Z",
        "policy_version": 1,
        "routing_tier": "TIER_1",
    }


def test_required_fields_count_and_names():
    """Verifies that exactly 11 security-critical fields are specified."""
    assert len(REQUIRED_PAYMENT_BUNDLE_FIELDS) == 11
    expected = {
        "vendor_id",
        "amount",
        "currency",
        "bank_account",
        "invoice_id",
        "po_id",
        "timestamp",
        "nonce",
        "expiry",
        "policy_version",
        "routing_tier",
    }
    assert REQUIRED_PAYMENT_BUNDLE_FIELDS == expected


def test_same_payment_produces_identical_canonical_json(baseline_bundle_data):
    """Test 1: Same payment bundle produces identical canonical representation."""
    bundle_a = create_payment_bundle(**baseline_bundle_data)
    bundle_b = create_payment_bundle(**baseline_bundle_data)

    canonical_a = canonicalize_payment_bundle(bundle_a)
    canonical_b = canonicalize_payment_bundle(bundle_b)

    assert canonical_a == canonical_b
    # Verify no insignificant whitespace exists in canonical output
    assert " " not in canonical_a
    assert "\n" not in canonical_a
    assert "\t" not in canonical_a


def test_same_payment_produces_identical_sha256_hash(baseline_bundle_data):
    """Test 2: Same payment produces identical SHA-256 hash."""
    bundle_a = create_payment_bundle(**baseline_bundle_data)
    bundle_b = create_payment_bundle(**baseline_bundle_data)

    hash_a = hash_payment_bundle(bundle_a)
    hash_b = hash_payment_bundle(bundle_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64
    assert hash_a.isalnum()


def test_key_insertion_order_independence(baseline_bundle_data):
    """Verifies canonicalization is deterministic regardless of dict insertion order."""
    # Insertion order 1 (standard)
    bundle_forward = dict(baseline_bundle_data)

    # Insertion order 2 (reversed)
    bundle_reversed = {k: baseline_bundle_data[k] for k in reversed(list(baseline_bundle_data.keys()))}

    # Insertion order 3 (shuffled keys)
    shuffled_keys = [
        "routing_tier", "timestamp", "vendor_id", "nonce", "amount",
        "po_id", "currency", "expiry", "invoice_id", "bank_account", "policy_version"
    ]
    bundle_shuffled = {k: baseline_bundle_data[k] for k in shuffled_keys}

    canonical_forward = canonicalize_payment_bundle(bundle_forward)
    canonical_reversed = canonicalize_payment_bundle(bundle_reversed)
    canonical_shuffled = canonicalize_payment_bundle(bundle_shuffled)

    assert canonical_forward == canonical_reversed
    assert canonical_reversed == canonical_shuffled

    assert hash_payment_bundle(bundle_forward) == hash_payment_bundle(bundle_reversed)
    assert hash_payment_bundle(bundle_reversed) == hash_payment_bundle(bundle_shuffled)


def test_different_amount_changes_hash(baseline_bundle_data):
    """Test 3: Altering amount changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, amount=500000)
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_vendor_id_changes_hash(baseline_bundle_data):
    """Test 4: Altering vendor_id changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, vendor_id="VEND-999")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_bank_account_changes_hash(baseline_bundle_data):
    """Test 5: Altering bank_account changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, bank_account="ROGUE-BANK-999")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_invoice_id_changes_hash(baseline_bundle_data):
    """Test 6: Altering invoice_id changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, invoice_id="INV-FORGED-002")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_po_id_changes_hash(baseline_bundle_data):
    """Test 7: Altering po_id (including None vs string) changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)

    # Modified PO string
    data_diff_po = dict(baseline_bundle_data, po_id="PO-2026-999")
    bundle_diff_po = create_payment_bundle(**data_diff_po)
    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_diff_po)

    # PO is None (null)
    data_null_po = dict(baseline_bundle_data, po_id=None)
    bundle_null_po = create_payment_bundle(**data_null_po)
    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_null_po)

    # Verify canonical null representation
    canonical_null = canonicalize_payment_bundle(bundle_null_po)
    assert '"po_id":null' in canonical_null


def test_different_currency_changes_hash(baseline_bundle_data):
    """Test 8: Altering currency changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, currency="USD")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_routing_tier_changes_hash(baseline_bundle_data):
    """Test 9: Altering routing_tier changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, routing_tier="AUTO_APPROVE")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_policy_version_changes_hash(baseline_bundle_data):
    """Test 10: Altering policy_version changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, policy_version=2)
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_nonce_changes_hash(baseline_bundle_data):
    """Test 11: Altering nonce changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, nonce="ffffffffffffffffffffffffffffffff")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_different_timestamp_changes_hash(baseline_bundle_data):
    """Test 12: Altering timestamp changes the cryptographic hash."""
    bundle_original = create_payment_bundle(**baseline_bundle_data)
    tampered_data = dict(baseline_bundle_data, timestamp="2026-10-06T12:00:01Z")
    bundle_tampered = create_payment_bundle(**tampered_data)

    assert hash_payment_bundle(bundle_original) != hash_payment_bundle(bundle_tampered)


def test_expired_bundle_detection(baseline_bundle_data):
    """Test 13: Detects and rejects expired payment bundles."""
    past_expiry = "2020-01-01T00:05:00Z"
    past_ts = "2020-01-01T00:00:00Z"
    expired_data = dict(baseline_bundle_data, timestamp=past_ts, expiry=past_expiry)
    expired_bundle = create_payment_bundle(**expired_data)

    assert is_bundle_expired(expired_bundle) is True

    with pytest.raises(PaymentBundleExpiredError, match="Payment bundle expired"):
        verify_bundle_not_expired(expired_bundle)

    # Valid future bundle
    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    future_data = dict(
        baseline_bundle_data,
        timestamp=datetime.now(timezone.utc),
        expiry=future_time,
    )
    valid_bundle = create_payment_bundle(**future_data)
    assert is_bundle_expired(valid_bundle) is False
    verify_bundle_not_expired(valid_bundle)  # Should not raise


def test_missing_required_fields_rejected(baseline_bundle_data):
    """Test 14a: Rejects bundles with missing required fields."""
    for field in REQUIRED_PAYMENT_BUNDLE_FIELDS:
        incomplete_data = dict(baseline_bundle_data)
        del incomplete_data[field]
        with pytest.raises(PaymentBundleValidationError, match="Missing required bundle field"):
            validate_payment_bundle(incomplete_data)


def test_extra_unknown_fields_rejected(baseline_bundle_data):
    """Test 14b: Rejects bundles containing unexpected extra fields."""
    rogue_data = dict(baseline_bundle_data, hacker_override="bypass_all_checks")
    with pytest.raises(PaymentBundleValidationError, match="Unexpected bundle field"):
        validate_payment_bundle(rogue_data)


@pytest.mark.parametrize("invalid_amount", [
    0,
    -100.50,
    "fifty_thousand",
    float("nan"),
    float("inf"),
    float("-inf"),
    True,
    False,
    None,
])
def test_invalid_amount_rejected(baseline_bundle_data, invalid_amount):
    """Test 14c: Rejects invalid, non-numeric, non-positive, or boolean amounts."""
    bad_data = dict(baseline_bundle_data, amount=invalid_amount)
    with pytest.raises(PaymentBundleValidationError):
        validate_payment_bundle(bad_data)


@pytest.mark.parametrize("bad_field,bad_val", [
    ("vendor_id", ""),
    ("vendor_id", "   "),
    ("currency", ""),
    ("bank_account", ""),
    ("invoice_id", ""),
    ("routing_tier", ""),
    ("policy_version", 0),
    ("policy_version", -1),
    ("policy_version", True),
    ("policy_version", "invalid"),
    ("nonce", "short"),
    ("timestamp", "not-a-date"),
    ("expiry", "invalid-date"),
])
def test_malformed_fields_rejected(baseline_bundle_data, bad_field, bad_val):
    """Test 14d: Rejects empty strings, invalid types, or malformed values."""
    bad_data = dict(baseline_bundle_data, **{bad_field: bad_val})
    with pytest.raises(PaymentBundleValidationError):
        validate_payment_bundle(bad_data)


def test_server_side_nonce_generation():
    """Test 15: Verifies nonces are generated server-side with high entropy."""
    nonces = [generate_payment_nonce() for _ in range(100)]
    # All 100 nonces must be unique
    assert len(set(nonces)) == 100
    for nonce in nonces:
        assert len(nonce) == 32  # 16 bytes = 32 hex chars
        assert all(c in "0123456789abcdef" for c in nonce)


def test_frontend_cannot_override_policy_or_routing():
    """Test 16: Verifies policy_version and routing_tier are bound to server models."""
    payment = PaymentRequest(
        request_id="REQ-TEST-001",
        vendor_id="VEND-001",
        amount=50000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-001",
        po_id="PO-001",
        timestamp=datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc),
        routing_tier="TIER_1",
    )

    trusted_policy_version = 1

    # Server builds bundle using authoritative backend model and policy
    trusted_bundle = create_payment_bundle_from_model(
        payment=payment,
        policy_version=trusted_policy_version,
    )

    assert trusted_bundle["routing_tier"] == "TIER_1"
    assert trusted_bundle["policy_version"] == 1

    # An attacker attempting to forge a bundle with AUTO_APPROVE or policy_version 99
    # will produce a different hash that the server's verification will detect
    attacker_forged_bundle = create_payment_bundle(
        vendor_id=payment.vendor_id,
        amount=payment.amount,
        currency=payment.currency,
        bank_account=payment.bank_account,
        invoice_id=payment.invoice_id,
        po_id=payment.po_id,
        timestamp=trusted_bundle["timestamp"],
        nonce=trusted_bundle["nonce"],
        expiry=trusted_bundle["expiry"],
        policy_version=99,  # Forged policy version
        routing_tier="AUTO_APPROVE",  # Forged routing tier
    )

    trusted_hash = hash_payment_bundle(trusted_bundle)
    forged_hash = hash_payment_bundle(attacker_forged_bundle)

    assert trusted_hash != forged_hash


def test_numeric_determinism_float_vs_int(baseline_bundle_data):
    """
    Verifies that float and int representations of whole numbers produce
    identical canonical representations and hashes.
    """
    data_int = dict(baseline_bundle_data, amount=50000)
    data_float = dict(baseline_bundle_data, amount=50000.0)
    data_decimal = dict(baseline_bundle_data, amount=Decimal("50000.00"))

    bundle_int = create_payment_bundle(**data_int)
    bundle_float = create_payment_bundle(**data_float)
    bundle_decimal = create_payment_bundle(**data_decimal)

    canonical_int = canonicalize_payment_bundle(bundle_int)
    canonical_float = canonicalize_payment_bundle(bundle_float)
    canonical_decimal = canonicalize_payment_bundle(bundle_decimal)

    assert canonical_int == canonical_float
    assert canonical_float == canonical_decimal

    assert hash_payment_bundle(bundle_int) == hash_payment_bundle(bundle_float)
    assert hash_payment_bundle(bundle_float) == hash_payment_bundle(bundle_decimal)

    # Fractional amounts format deterministically
    data_frac = dict(baseline_bundle_data, amount=50000.25)
    bundle_frac = create_payment_bundle(**data_frac)
    assert '"amount":50000.25' in canonicalize_payment_bundle(bundle_frac)


def test_tamper_detection_avalanche_effect(baseline_bundle_data):
    """
    Demonstrates tamper foundation: modifying a single digit in amount
    completely alters the SHA-256 hash.
    """
    bundle_orig = create_payment_bundle(**baseline_bundle_data)
    bundle_tampered = create_payment_bundle(**dict(baseline_bundle_data, amount=50001))

    hash_orig = hash_payment_bundle(bundle_orig)
    hash_tampered = hash_payment_bundle(bundle_tampered)

    assert hash_orig != hash_tampered

    # Count differing hex characters to demonstrate avalanche effect
    diff_chars = sum(c1 != c2 for c1, c2 in zip(hash_orig, hash_tampered))
    assert diff_chars > 30  # Substantial divergence in 64-char hex digest


def test_timestamp_and_expiry_helpers():
    """Validates timestamp parsing, formatting, and TTL calculation."""
    dt = datetime(2026, 10, 6, 12, 0, 0, tzinfo=timezone.utc)
    ts_str = format_utc_timestamp(dt)
    assert ts_str == "2026-10-06T12:00:00Z"

    parsed = parse_utc_timestamp("2026-10-06T12:00:00Z")
    assert parsed.tzinfo == timezone.utc
    assert parsed.year == 2026
    assert parsed.hour == 12

    # Test expiry calculation with 300s TTL
    expiry_str = calculate_bundle_expiry(ttl_seconds=300, base_time=dt)
    assert expiry_str == "2026-10-06T12:05:00Z"
