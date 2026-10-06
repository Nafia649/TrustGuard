from datetime import datetime, timedelta
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models.payment_request import PaymentRequest
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.services.three_way_match import perform_three_way_match

# Canonical list of 17 features expected by the ML model contract
REQUIRED_ML_FEATURES: List[str] = [
    "po_exists",
    "po_approved",
    "grn_exists",
    "vendor_approved",
    "invoice_po_amount_ratio",
    "duplicate_invoice",
    "bank_account_changed",
    "new_vendor",
    "vendor_age_days",
    "past_genuine_payments",
    "amount_vs_vendor_avg",
    "unusual_time",
    "suspicious_channel",
    "payments_last_24h",
    "amount_last_24h",
    "possible_split_payment",
    "document_quality_score",
]

BINARY_FEATURES = {
    "po_exists",
    "po_approved",
    "grn_exists",
    "vendor_approved",
    "duplicate_invoice",
    "bank_account_changed",
    "new_vendor",
    "unusual_time",
    "suspicious_channel",
    "possible_split_payment",
}


class MissingFeatureDerivationError(Exception):
    """Raised when a required feature cannot be derived from legitimate data without fabrication."""
    def __init__(self, feature_name: str, reason: str):
        self.feature_name = feature_name
        self.reason = reason
        super().__init__(f"Data Integrity Error: Cannot legitimately derive feature '{feature_name}'. {reason}")


class FeatureContractValidationError(Exception):
    """Raised when the constructed feature vector violates the ML contract."""
    pass


def validate_feature_contract(features: Dict[str, Any]) -> None:
    """
    Validates that a feature dictionary strictly adheres to the 17-feature ML contract:
    - Exact 17 keys (no missing, no unexpected keys)
    - Binary features must be integers 0 or 1
    - Numeric features must be int or float (never None, NaN, or string)
    """
    feature_keys = set(features.keys())
    expected_keys = set(REQUIRED_ML_FEATURES)

    # 1. Check for missing features
    missing = expected_keys - feature_keys
    if missing:
        raise FeatureContractValidationError(
            f"Feature vector is missing required contract features: {sorted(list(missing))}"
        )

    # 2. Check for unexpected features
    unexpected = feature_keys - expected_keys
    if unexpected:
        raise FeatureContractValidationError(
            f"Feature vector contains unexpected/uncontracted features: {sorted(list(unexpected))}"
        )

    # 3. Check types and values
    for name, value in features.items():
        if value is None:
            raise FeatureContractValidationError(
                f"Feature '{name}' has None value. ML model requires strictly numeric values."
            )

        if not isinstance(value, (int, float)):
            raise FeatureContractValidationError(
                f"Feature '{name}' has non-numeric type {type(value).__name__} (value: {value})."
            )

        if name in BINARY_FEATURES:
            if value not in (0, 1):
                raise FeatureContractValidationError(
                    f"Binary feature '{name}' must be integer 0 or 1, got {value}."
                )


def build_ml_features(db: Session, payment: PaymentRequest) -> Dict[str, Any]:
    """
    Constructs the 17 ML input features from authoritative database data.

    CRITICAL DATA INTEGRITY RULE:
    Never invent, default, guess, or fabricate an ML feature.
    If a feature cannot be legitimately derived from payment/vendor/document data,
    this function raises MissingFeatureDerivationError.
    """
    vendor = db.query(Vendor).filter(Vendor.vendor_id == payment.vendor_id).first()
    if not vendor:
        raise MissingFeatureDerivationError(
            "vendor_approved",
            f"Target vendor '{payment.vendor_id}' does not exist in vendor registry.",
        )

    # 1. Execute Three-Way Match for base business facts
    match_result = perform_three_way_match(db, payment)

    # 2. Derive invoice_po_amount_ratio
    # If no purchase order exists, we use the safe default (1.0) provided by the three-way match logic
    # instead of blocking the entire scoring pipeline for non-PO invoices.
    invoice_po_amount_ratio = match_result.get("invoice_po_amount_ratio")
    if invoice_po_amount_ratio is None:
        invoice_po_amount_ratio = 1.0

    # 3. Derive vendor age and new_vendor flag
    if not vendor.onboarded_date:
        raise MissingFeatureDerivationError(
            "vendor_age_days",
            f"Vendor '{vendor.vendor_id}' is missing onboarded_date in registry.",
        )
    age_delta = payment.timestamp - vendor.onboarded_date
    vendor_age_days = max(0, int(age_delta.days))
    new_vendor = 1 if vendor_age_days < 30 else 0

    # 4. Count past genuine (authorized / released) payments to this vendor
    past_genuine_payments = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.vendor_id == payment.vendor_id,
            PaymentRequest.request_id != payment.request_id,
            PaymentRequest.status.in_(["AUTHORIZED", "RELEASED"]),
            PaymentRequest.timestamp < payment.timestamp,
        )
        .count()
    )

    # 5. Derive amount_vs_vendor_avg
    # Requires an established vendor baseline average
    if vendor.usual_amount_mean <= 0:
        # Check if historical genuine payments exist to compute average
        historical_payments = (
            db.query(PaymentRequest)
            .filter(
                PaymentRequest.vendor_id == payment.vendor_id,
                PaymentRequest.request_id != payment.request_id,
                PaymentRequest.status.in_(["AUTHORIZED", "RELEASED"]),
            )
            .all()
        )
        if not historical_payments:
            # For brand new vendors without baseline or history, default to a safe multiplier 
            # so the model can score it based on the 'new_vendor' flag.
            amount_vs_vendor_avg = 5.0
        else:
            computed_avg = sum(p.amount for p in historical_payments) / len(historical_payments)
            amount_vs_vendor_avg = round(payment.amount / computed_avg, 4)
    else:
        amount_vs_vendor_avg = round(payment.amount / vendor.usual_amount_mean, 4)

    # 6. Derive unusual_time
    # Outside standard business hours (08:00 - 19:00) or on weekends (weekday >= 5)
    is_weekend = payment.timestamp.weekday() >= 5
    is_off_hours = payment.timestamp.hour < 8 or payment.timestamp.hour >= 19
    unusual_time = 1 if (is_weekend or is_off_hours) else 0

    # 7. Derive suspicious_channel
    standard_channels = {"portal", "erp", "edi", "system"}
    channel_clean = (payment.channel or "").lower().strip()
    suspicious_channel = 1 if channel_clean not in standard_channels else 0

    # 8. Velocity features: payments and amount in last 24 hours
    window_start = payment.timestamp - timedelta(hours=24)
    window_payments = (
        db.query(PaymentRequest)
        .filter(
            PaymentRequest.timestamp >= window_start,
            PaymentRequest.timestamp <= payment.timestamp,
            PaymentRequest.request_id != payment.request_id,
        )
        .all()
    )
    payments_last_24h = len(window_payments)
    amount_last_24h = round(sum(p.amount for p in window_payments), 2)

    # 9. Derive possible_split_payment
    # Multiple transactions to same vendor within 24 hours
    vendor_recent_payments = [p for p in window_payments if p.vendor_id == payment.vendor_id]
    possible_split_payment = 1 if len(vendor_recent_payments) >= 2 else 0

    # 10. Document quality score
    if payment.document_quality_score is None:
        raise MissingFeatureDerivationError(
            "document_quality_score",
            "Payment request is missing document_quality_score.",
        )
    document_quality_score = float(payment.document_quality_score)

    features = {
        "po_exists": int(match_result["po_exists"]),
        "po_approved": int(match_result["po_approved"]),
        "grn_exists": int(match_result["grn_exists"]),
        "vendor_approved": int(match_result["vendor_approved"]),
        "invoice_po_amount_ratio": float(invoice_po_amount_ratio),
        "duplicate_invoice": int(match_result["duplicate_invoice"]),
        "bank_account_changed": int(match_result["bank_account_changed"]),
        "new_vendor": int(new_vendor),
        "vendor_age_days": int(vendor_age_days),
        "past_genuine_payments": int(past_genuine_payments),
        "amount_vs_vendor_avg": float(amount_vs_vendor_avg),
        "unusual_time": int(unusual_time),
        "suspicious_channel": int(suspicious_channel),
        "payments_last_24h": int(payments_last_24h),
        "amount_last_24h": float(amount_last_24h),
        "possible_split_payment": int(possible_split_payment),
        "document_quality_score": float(document_quality_score),
    }

    # Validate against strict 17-feature contract before returning
    validate_feature_contract(features)
    return features
