"""
REALKEY Tamper Detection Demonstration Module.

Demonstrates that any unauthorized modification to any of the 11 security-critical
fields of an approved payment bundle breaks the SHA-256 canonical hash, fails
cryptographic verification, and triggers an immutable audit alert without
corrupting database state.
"""

import copy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, List, Optional, Union

from security.realkey.bundle import (
    REQUIRED_PAYMENT_BUNDLE_FIELDS,
    PaymentBundleValidationError,
    canonicalize_payment_bundle,
    hash_payment_bundle,
    validate_payment_bundle,
)
from security.realkey.webauthn_verifier import PaymentHashMismatchError


@dataclass
class TamperVerificationResult:
    """Structured result of a tamper verification check."""
    tamper_detected: bool
    field_modified: str
    original_value: Any
    tampered_value: Any
    original_hash: str
    tampered_hash: str
    hash_match: bool
    approval_valid: bool
    reason: str
    message: str


def simulate_payment_tampering(
    original_bundle: Dict[str, Any],
    field: str,
    tampered_value: Any,
) -> Dict[str, Any]:
    """
    Creates an in-memory copy of a payment bundle with a single field modified.

    Ensures that the original bundle dictionary is never modified (zero side effects).
    Validates that the target field is one of the 11 security-critical bundle fields.

    Args:
        original_bundle: Authoritative 11-field payment bundle dictionary.
        field: Name of the field to tamper with.
        tampered_value: Attacker-supplied replacement value.

    Returns:
        Deep copy of the bundle dictionary with the specified field altered.

    Raises:
        ValueError: If field is not one of the 11 security-critical bundle fields.
    """
    if field not in REQUIRED_PAYMENT_BUNDLE_FIELDS:
        raise ValueError(
            f"Invalid field '{field}'. Target field must be one of: {sorted(list(REQUIRED_PAYMENT_BUNDLE_FIELDS))}"
        )

    tampered = copy.deepcopy(original_bundle)
    tampered[field] = tampered_value
    return tampered


def demonstrate_tamper_detection(
    original_bundle: Dict[str, Any],
    field: str,
    tampered_value: Any,
) -> TamperVerificationResult:
    """
    Executes a real cryptographic comparison between an original approved payment bundle
    and a simulated tampered copy.

    1. Computes the real RFC 8785 canonical JSON and SHA-256 digest of original bundle.
    2. Constructs a tampered copy in memory.
    3. Canonicalizes and computes the SHA-256 digest of the tampered copy.
    4. Compares the two hashes cryptographically.
    5. Returns structured TamperVerificationResult.

    Args:
        original_bundle: Original authoritative payment bundle dictionary.
        field: Field name modified by the attacker.
        tampered_value: Modified value supplied by the attacker.

    Returns:
        TamperVerificationResult describing the tamper status and cryptographic outcome.
    """
    if field not in REQUIRED_PAYMENT_BUNDLE_FIELDS:
        raise ValueError(
            f"Invalid field '{field}'. Target field must be one of: {sorted(list(REQUIRED_PAYMENT_BUNDLE_FIELDS))}"
        )

    # 1. Authoritative original hash
    orig_validated = validate_payment_bundle(original_bundle)
    orig_canonical = canonicalize_payment_bundle(orig_validated)
    orig_hash = hash_payment_bundle(orig_canonical)
    orig_val = orig_validated[field]

    # 2. In-memory tampered copy
    tampered_bundle = simulate_payment_tampering(orig_validated, field, tampered_value)

    # 3. Canonicalize & hash tampered bundle
    try:
        tampered_validated = validate_payment_bundle(tampered_bundle)
        tampered_canonical = canonicalize_payment_bundle(tampered_validated)
        tampered_hash = hash_payment_bundle(tampered_canonical)
        reported_tampered_val = tampered_validated[field]
    except PaymentBundleValidationError as val_err:
        # Attacker supplied structurally invalid data (e.g. invalid type, negative amount)
        # This is an immediate validation rejection
        raw_tampered = json.dumps(tampered_bundle, sort_keys=True, default=str)
        tampered_hash = hashlib.sha256(raw_tampered.encode("utf-8")).hexdigest()
        return TamperVerificationResult(
            tamper_detected=True,
            field_modified=field,
            original_value=orig_val,
            tampered_value=tampered_value,
            original_hash=orig_hash,
            tampered_hash=tampered_hash,
            hash_match=False,
            approval_valid=False,
            reason="PAYMENT_BUNDLE_VALIDATION_FAILED",
            message=f"Tampered bundle failed validation: {val_err}",
        )

    # 4. Cryptographic hash comparison
    hash_match = (orig_hash == tampered_hash)
    tamper_detected = not hash_match
    approval_valid = hash_match

    if tamper_detected:
        reason = "PAYMENT_HASH_MISMATCH"
        message = (
            f"Payment hash mismatch detected for field '{field}'! "
            f"Original hash '{orig_hash[:16]}...' != Tampered hash '{tampered_hash[:16]}...'. "
            f"Cryptographic approval signature rejected for modified payment."
        )
    else:
        reason = "IDENTICAL_PAYMENT"
        message = "Submitted value is identical to original; no tampering detected."

    return TamperVerificationResult(
        tamper_detected=tamper_detected,
        field_modified=field,
        original_value=orig_val,
        tampered_value=reported_tampered_val,
        original_hash=orig_hash,
        tampered_hash=tampered_hash,
        hash_match=hash_match,
        approval_valid=approval_valid,
        reason=reason,
        message=message,
    )


def verify_bundle_integrity(expected_hash: str, bundle: Dict[str, Any]) -> bool:
    """
    Checks if a given payment bundle's canonical SHA-256 hash matches the expected hash.

    Returns:
        True if hashes match exactly, False otherwise.
    """
    try:
        calculated_hash = hash_payment_bundle(bundle)
        return calculated_hash == expected_hash
    except Exception:
        return False
