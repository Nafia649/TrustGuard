"""
REALKEY Canonical Payment Bundle Module.

Provides deterministic canonical serialization (RFC 8785 / JCS compliant),
cryptographic SHA-256 hashing, server-side nonce generation, and expiry
protection for exact payment authorization in TrustGuard.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import math
import secrets
from typing import Any, Dict, Optional, Set, Union

DEFAULT_BUNDLE_TTL_SECONDS: int = 300

try:
    from app.config import settings
    DEFAULT_BUNDLE_TTL_SECONDS = getattr(settings, "WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS", 300)
except ImportError:
    settings = None


class PaymentBundleError(Exception):
    """Base exception for payment bundle errors."""
    pass


class PaymentBundleValidationError(PaymentBundleError):
    """Raised when payment bundle structure or fields fail validation."""
    pass


class PaymentBundleExpiredError(PaymentBundleError):
    """Raised when a payment bundle has exceeded its time-to-live."""
    pass


REQUIRED_PAYMENT_BUNDLE_FIELDS: Set[str] = {
    "amount",
    "bank_account",
    "currency",
    "expiry",
    "invoice_id",
    "nonce",
    "po_id",
    "policy_version",
    "routing_tier",
    "timestamp",
    "vendor_id",
}


def generate_payment_nonce() -> str:
    """
    Generates a cryptographically secure, unpredictable random nonce for payment signing.
    
    Uses secrets.token_hex(16) to provide 128 bits of cryptographic entropy.
    Independent of WebAuthn ceremony challenges.
    """
    return secrets.token_hex(16)


def parse_utc_timestamp(val: Union[datetime, str]) -> datetime:
    """
    Parses a timestamp string or datetime into a timezone-aware UTC datetime.
    """
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, str):
        s = val.strip()
        if not s:
            raise PaymentBundleValidationError("Timestamp string cannot be empty.")
        try:
            if s.endswith("Z"):
                dt = datetime.fromisoformat(s[:-1] + "+00:00")
            else:
                dt = datetime.fromisoformat(s)
        except Exception as e:
            raise PaymentBundleValidationError(f"Invalid ISO-8601 timestamp '{val}': {e}")
    else:
        raise PaymentBundleValidationError(
            f"Timestamp must be datetime or ISO string, got {type(val).__name__}."
        )

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_utc_timestamp(dt: datetime) -> str:
    """
    Formats a datetime object as a canonical ISO-8601 UTC string ending in 'Z'.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    if dt.microsecond == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def calculate_bundle_expiry(
    ttl_seconds: Optional[int] = None,
    base_time: Optional[Union[datetime, str]] = None,
) -> str:
    """
    Calculates the expiration timestamp for a payment bundle in UTC ISO-8601 format.
    
    Args:
        ttl_seconds: Time-to-live in seconds. Defaults to WEBAUTHN_CHALLENGE_TIMEOUT_SECONDS (300).
        base_time: Reference base time. Defaults to current UTC time.
    """
    ttl = (
        ttl_seconds
        if ttl_seconds is not None
        else DEFAULT_BUNDLE_TTL_SECONDS
    )
    if ttl <= 0:
        raise PaymentBundleValidationError("TTL seconds must be greater than zero.")

    if base_time is not None:
        ref_dt = parse_utc_timestamp(base_time)
    else:
        ref_dt = datetime.now(timezone.utc)

    expiry_dt = ref_dt + timedelta(seconds=ttl)
    return format_utc_timestamp(expiry_dt)


def normalize_amount(val: Any) -> Union[int, float]:
    """
    Normalizes a monetary amount deterministically to prevent float serialization divergence.
    """
    if isinstance(val, bool):
        raise PaymentBundleValidationError("Amount cannot be a boolean.")
    if isinstance(val, Decimal):
        val = float(val)
    if not isinstance(val, (int, float)):
        raise PaymentBundleValidationError(
            f"Amount must be a numeric value, got {type(val).__name__}."
        )
    if math.isnan(val) or math.isinf(val):
        raise PaymentBundleValidationError("Amount cannot be NaN or Infinity.")
    if val <= 0:
        raise PaymentBundleValidationError("Amount must be greater than zero.")

    rounded = round(float(val), 2)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def normalize_policy_version(val: Any) -> int:
    """
    Normalizes and validates the policy version integer.
    """
    if isinstance(val, bool):
        raise PaymentBundleValidationError("policy_version cannot be a boolean.")
    if isinstance(val, int):
        int_val = val
    elif isinstance(val, str) and val.strip().isdigit():
        int_val = int(val.strip())
    else:
        raise PaymentBundleValidationError(
            f"policy_version must be a positive integer, got {val!r}."
        )
    if int_val < 1:
        raise PaymentBundleValidationError(
            f"policy_version must be >= 1, got {int_val}."
        )
    return int_val


def validate_payment_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates all 11 security-critical fields of the payment bundle and returns
    a normalized dictionary with exact types and canonical formats.
    
    Rejects missing fields, extraneous fields, invalid formats, or non-positive amounts.
    """
    if not isinstance(bundle, dict):
        raise PaymentBundleValidationError(f"Payment bundle must be a dict, got {type(bundle).__name__}.")

    bundle_keys = set(bundle.keys())
    missing = REQUIRED_PAYMENT_BUNDLE_FIELDS - bundle_keys
    if missing:
        raise PaymentBundleValidationError(
            f"Missing required bundle field(s): {sorted(list(missing))}"
        )
    extra = bundle_keys - REQUIRED_PAYMENT_BUNDLE_FIELDS
    if extra:
        raise PaymentBundleValidationError(
            f"Unexpected bundle field(s): {sorted(list(extra))}"
        )

    # 1. vendor_id
    vendor_id = bundle["vendor_id"]
    if not isinstance(vendor_id, str) or not vendor_id.strip():
        raise PaymentBundleValidationError("vendor_id must be a non-empty string.")

    # 2. amount
    amount = normalize_amount(bundle["amount"])

    # 3. currency
    currency = bundle["currency"]
    if not isinstance(currency, str) or not currency.strip():
        raise PaymentBundleValidationError("currency must be a non-empty string.")

    # 4. bank_account
    bank_account = bundle["bank_account"]
    if not isinstance(bank_account, str) or not bank_account.strip():
        raise PaymentBundleValidationError("bank_account must be a non-empty string.")

    # 5. invoice_id
    invoice_id = bundle["invoice_id"]
    if not isinstance(invoice_id, str) or not invoice_id.strip():
        raise PaymentBundleValidationError("invoice_id must be a non-empty string.")

    # 6. po_id (optional: None or non-empty string)
    po_id_val = bundle["po_id"]
    if po_id_val is None:
        po_id = None
    elif isinstance(po_id_val, str):
        stripped = po_id_val.strip()
        po_id = stripped if stripped else None
    else:
        raise PaymentBundleValidationError(
            f"po_id must be a string or None, got {type(po_id_val).__name__}."
        )

    # 7. timestamp
    ts_dt = parse_utc_timestamp(bundle["timestamp"])
    timestamp_str = format_utc_timestamp(ts_dt)

    # 8. nonce
    nonce_val = bundle["nonce"]
    if not isinstance(nonce_val, str) or len(nonce_val.strip()) < 8:
        raise PaymentBundleValidationError("nonce must be a string with at least 8 characters.")

    # 9. expiry
    exp_dt = parse_utc_timestamp(bundle["expiry"])
    expiry_str = format_utc_timestamp(exp_dt)

    # 10. policy_version
    policy_version = normalize_policy_version(bundle["policy_version"])

    # 11. routing_tier
    routing_tier_val = bundle["routing_tier"]
    if not isinstance(routing_tier_val, str) or not routing_tier_val.strip():
        raise PaymentBundleValidationError("routing_tier must be a non-empty string.")

    return {
        "amount": amount,
        "bank_account": bank_account.strip(),
        "currency": currency.strip().upper(),
        "expiry": expiry_str,
        "invoice_id": invoice_id.strip(),
        "nonce": nonce_val.strip(),
        "po_id": po_id,
        "policy_version": policy_version,
        "routing_tier": routing_tier_val.strip().upper(),
        "timestamp": timestamp_str,
        "vendor_id": vendor_id.strip(),
    }


def create_payment_bundle(
    vendor_id: str,
    amount: Union[int, float, Decimal],
    currency: str,
    bank_account: str,
    invoice_id: str,
    po_id: Optional[str] = None,
    timestamp: Optional[Union[datetime, str]] = None,
    nonce: Optional[str] = None,
    expiry: Optional[Union[datetime, str]] = None,
    policy_version: int = 1,
    routing_tier: str = "TIER_1",
    ttl_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs a validated 11-field canonical payment bundle.
    
    If nonce, timestamp, or expiry are not provided, they are securely generated server-side.
    """
    if timestamp is None:
        ts_dt = datetime.now(timezone.utc)
        ts_str = format_utc_timestamp(ts_dt)
    else:
        ts_dt = parse_utc_timestamp(timestamp)
        ts_str = format_utc_timestamp(ts_dt)

    if nonce is None:
        nonce_str = generate_payment_nonce()
    else:
        nonce_str = str(nonce).strip()

    if expiry is None:
        expiry_str = calculate_bundle_expiry(ttl_seconds=ttl_seconds, base_time=ts_dt)
    else:
        expiry_str = format_utc_timestamp(parse_utc_timestamp(expiry))

    raw_bundle = {
        "vendor_id": vendor_id,
        "amount": amount,
        "currency": currency,
        "bank_account": bank_account,
        "invoice_id": invoice_id,
        "po_id": po_id,
        "timestamp": ts_str,
        "nonce": nonce_str,
        "expiry": expiry_str,
        "policy_version": policy_version,
        "routing_tier": routing_tier,
    }

    return validate_payment_bundle(raw_bundle)


def create_payment_bundle_from_model(
    payment: Any,
    policy_version: int,
    routing_tier: Optional[str] = None,
    ttl_seconds: Optional[int] = None,
    nonce: Optional[str] = None,
    current_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Binds a database PaymentRequest model and server-side policy metadata
    into a canonical payment bundle.
    
    Guarantees policy_version and routing_tier are sourced from backend authority,
    preventing any frontend or client override.
    """
    resolved_tier = routing_tier or getattr(payment, "routing_tier", None)
    if not resolved_tier:
        raise PaymentBundleValidationError(
            "Routing tier must be determined by the backend policy engine before creating bundle."
        )

    ceremony_time = current_time or datetime.now(timezone.utc)
    payment_time = getattr(payment, "timestamp", None) or ceremony_time

    return create_payment_bundle(
        vendor_id=payment.vendor_id,
        amount=payment.amount,
        currency=payment.currency,
        bank_account=payment.bank_account,
        invoice_id=payment.invoice_id,
        po_id=getattr(payment, "po_id", None),
        timestamp=payment_time,
        nonce=nonce or generate_payment_nonce(),
        expiry=calculate_bundle_expiry(ttl_seconds=ttl_seconds, base_time=ceremony_time),
        policy_version=policy_version,
        routing_tier=resolved_tier,
    )


def canonicalize_payment_bundle(bundle: Dict[str, Any]) -> str:
    """
    Produces the deterministic canonical JSON string representation of a payment bundle.
    
    Compliant with RFC 8785 (JSON Canonicalization Scheme - JCS):
    - Keys sorted lexicographically by Unicode code points
    - Compact separators (',', ':') without whitespace
    - UTF-8 clean encoding without BOM
    - Deterministic numbers and null literals
    """
    validated = validate_payment_bundle(bundle)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def hash_payment_bundle(bundle_or_canonical: Union[Dict[str, Any], str, bytes]) -> str:
    """
    Computes the SHA-256 cryptographic digest of a canonical payment bundle.
    
    Returns:
        64-character lowercase hexadecimal string digest.
    """
    if isinstance(bundle_or_canonical, dict):
        canonical_str = canonicalize_payment_bundle(bundle_or_canonical)
        canonical_bytes = canonical_str.encode("utf-8")
    elif isinstance(bundle_or_canonical, str):
        canonical_bytes = bundle_or_canonical.encode("utf-8")
    elif isinstance(bundle_or_canonical, bytes):
        canonical_bytes = bundle_or_canonical
    else:
        raise PaymentBundleValidationError(
            f"Expected dict, str, or bytes to hash, got {type(bundle_or_canonical).__name__}."
        )

    return hashlib.sha256(canonical_bytes).hexdigest()


def is_bundle_expired(
    bundle: Dict[str, Any],
    current_time: Optional[datetime] = None,
) -> bool:
    """
    Checks whether a payment bundle has expired according to its expiry field.
    """
    if not isinstance(bundle, dict):
        raise PaymentBundleValidationError("Bundle must be a dictionary.")
    expiry_val = bundle.get("expiry")
    if not expiry_val:
        raise PaymentBundleValidationError("Bundle is missing 'expiry' field.")

    expiry_dt = parse_utc_timestamp(expiry_val)
    now = current_time if current_time is not None else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return now >= expiry_dt


def verify_bundle_not_expired(
    bundle: Dict[str, Any],
    current_time: Optional[datetime] = None,
) -> None:
    """
    Asserts that the bundle has not expired, raising PaymentBundleExpiredError if it has.
    """
    if is_bundle_expired(bundle, current_time=current_time):
        raise PaymentBundleExpiredError(
            f"Payment bundle expired at {bundle.get('expiry')}."
        )
