import logging
from typing import Any, Callable, Dict, List, Optional
from app.config import settings
from app.services.feature_builder import validate_feature_contract

logger = logging.getLogger(__name__)


def mock_predict_risk(features: Dict[str, Any]) -> Dict[str, Any]:
    """
    DETERMINISTIC MOCK ML PROVIDER (FOR TESTING / MVP DEVELOPMENT ONLY).

    Clearly labeled: This is NOT the real XGBoost + SHAP model.
    It produces deterministic intelligence from features solely for testing the backend
    orchestration layer when the ML package is not yet importable.
    """
    score = 15.0  # Low-risk baseline

    reasons: List[Dict[str, str]] = []

    # Check key fraud indicators per ML scenario design
    if features.get("po_exists") == 0:
        score += 35.0
        reasons.append({
            "feature": "po_exists",
            "impact": "high",
            "description": "Invoice submitted without a valid purchase order",
        })

    if features.get("vendor_approved") == 0:
        score += 30.0
        reasons.append({
            "feature": "vendor_approved",
            "impact": "high",
            "description": "Vendor is not on the approved vendor list",
        })

    if features.get("bank_account_changed") == 1:
        score += 25.0
        reasons.append({
            "feature": "bank_account_changed",
            "impact": "high",
            "description": "Beneficiary bank account differs from registered vendor account",
        })

    ratio = features.get("invoice_po_amount_ratio", 1.0)
    if ratio > 1.05:
        score += min(30.0, (ratio - 1.0) * 50.0)
        reasons.append({
            "feature": "invoice_po_amount_ratio",
            "impact": "medium",
            "description": f"Invoice amount exceeds purchase order by {(ratio - 1.0) * 100:.1f}%",
        })

    if features.get("duplicate_invoice") == 1:
        score += 35.0
        reasons.append({
            "feature": "duplicate_invoice",
            "impact": "high",
            "description": "Duplicate invoice submission detected for this vendor",
        })

    if features.get("unusual_time") == 1:
        score += 10.0
        reasons.append({
            "feature": "unusual_time",
            "impact": "low",
            "description": "Payment submitted outside normal business operating hours",
        })

    if features.get("suspicious_channel") == 1:
        score += 15.0
        reasons.append({
            "feature": "suspicious_channel",
            "impact": "medium",
            "description": "Payment submitted via unverified or manual communication channel",
        })

    if features.get("new_vendor") == 1 and features.get("amount_vs_vendor_avg", 1.0) > 2.0:
        score += 25.0
        reasons.append({
            "feature": "new_vendor_large_payment",
            "impact": "high",
            "description": "New vendor with payment significantly higher than average",
        })

    # Bound risk score between 0 and 100
    risk_score = int(min(100, max(0, round(score))))
    fraud_probability = round(risk_score / 100.0, 4)

    return {
        "fraud_probability": fraud_probability,
        "risk_score": risk_score,
        "reasons": reasons[:3],  # Top 3 explanations
    }


class MLClient:
    """
    ML Integration Adapter.
    Strictly responsible for:
    1. Validating the 17-feature contract
    2. Calling predict_risk(features)
    3. Returning intelligence: {fraud_probability, risk_score, reasons}

    The backend NEVER trains the model or duplicates ML algorithms.
    """
    def __init__(self, custom_predictor: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None):
        self._custom_predictor = custom_predictor

    def predict_risk(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes ML model inference for a transaction's 17-feature vector.
        Enforces strict contract validation before dispatch.
        """
        # Validate 17-feature contract
        validate_feature_contract(features)

        # 1. If custom predictor injected (e.g. for testing)
        if self._custom_predictor is not None:
            return self._custom_predictor(features)

        # 2. Attempt import of teammate's ML prediction module if configured
        if settings.ML_PROVIDER != "mock":
            try:
                # Target interface contract defined by ML teammate
                from ml.predict import predict_risk as ml_predict  # type: ignore
                return ml_predict(features)
            except ImportError as err:
                logger.warning(
                    "ML module 'ml.predict' not found. Falling back to mock adapter. Error: %s",
                    err,
                )

        # 3. Default to deterministic mock provider
        return mock_predict_risk(features)


# Default client instance
ml_client = MLClient()
