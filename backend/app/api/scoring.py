import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.payment_request import PaymentRequest
from app.services.three_way_match import perform_three_way_match
from app.services.feature_builder import (
    build_ml_features,
    MissingFeatureDerivationError,
    FeatureContractValidationError,
)
from app.services.ml_client import ml_client
from app.services.audit_service import log_event

router = APIRouter(tags=["Scoring"])


class BusinessChecksResponse(BaseModel):
    po_exists: int
    po_approved: int
    grn_exists: int
    goods_received: int
    vendor_approved: int
    amount_match: bool
    invoice_po_amount_ratio: Optional[float] = None
    duplicate_invoice: int
    bank_account_match: bool
    bank_account_changed: int
    details: Dict[str, Any]


class MLAssessmentResponse(BaseModel):
    fraud_probability: float
    risk_score: int
    reasons: List[Any]


class PaymentScoreResponse(BaseModel):
    request_id: str
    payment_status: str
    business_checks: BusinessChecksResponse
    ml_assessment: MLAssessmentResponse
    features_used: Dict[str, Any]


@router.post(
    "/payments/{request_id}/score",
    response_model=PaymentScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate payment risk using Three-Way Match facts and ML intelligence",
)
def score_payment(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Orchestrates the scoring pipeline:
    1. Loads payment request
    2. Runs Three-Way Matching business checks (deterministic facts)
    3. Derives legitimate ML features (fails if data is missing without fabrication)
    4. Calls ML adapter predict_risk(features)
    5. Records fraud score and explanations on the payment record
    6. Does NOT make final policy/approval decisions (reserved for Policy Engine)
    """
    # 1. Fetch payment request
    payment = (
        db.query(PaymentRequest)
        .filter(PaymentRequest.request_id == request_id)
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment request '{request_id}' not found.",
        )

    # 2. Perform Three-Way Match business checks
    three_way_facts = perform_three_way_match(db, payment)

    # 3. Construct 17 ML features adhering to the Data Integrity Rule
    try:
        features = build_ml_features(db, payment)
    except MissingFeatureDerivationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "MissingFeatureDerivationError",
                "feature": err.feature_name,
                "message": str(err),
                "business_checks": three_way_facts,
            },
        )
    except FeatureContractValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "FeatureContractValidationError",
                "message": str(err),
            },
        )

    # 4. Invoke ML Adapter (predict_risk)
    ml_result = ml_client.predict_risk(features)

    # 5. Store ML assessment on payment record
    payment.fraud_probability = ml_result["fraud_probability"]
    payment.risk_score = ml_result["risk_score"]
    payment.risk_reasons = json.dumps(ml_result["reasons"])
    # Transition status from PENDING to SCORED without approving
    if payment.status == "PENDING":
        payment.status = "SCORED"

    db.commit()
    db.refresh(payment)

    # 6. Audit log the scoring event
    log_event(
        db=db,
        user_id="trustguard_scoring_orchestrator",
        action="PAYMENT_SCORED",
        result="SUCCESS",
        request_id=payment.request_id,
        details={
            "risk_score": ml_result["risk_score"],
            "fraud_probability": ml_result["fraud_probability"],
            "reasons_count": len(ml_result["reasons"]),
            "three_way_po_exists": three_way_facts["po_exists"],
            "three_way_amount_match": three_way_facts["amount_match"],
        },
    )

    return PaymentScoreResponse(
        request_id=payment.request_id,
        payment_status=payment.status,
        business_checks=BusinessChecksResponse(**three_way_facts),
        ml_assessment=MLAssessmentResponse(**ml_result),
        features_used=features,
    )
