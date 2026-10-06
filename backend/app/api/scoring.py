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
from app.services.policy_engine import evaluate_routing
from app.schemas.policy import RoutingResult
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
    routing: RoutingResult
    features_used: Dict[str, Any]


@router.post(
    "/payments/{request_id}/score",
    response_model=PaymentScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate payment risk and determine approval routing tier",
)
def score_payment(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Orchestrates the complete scoring & routing pipeline:
    1. Loads payment request
    2. Runs Three-Way Matching business checks (deterministic facts)
    3. Derives legitimate ML features (fails if data is missing without fabrication)
    4. Calls ML adapter predict_risk(features)
    5. Evaluates configurable Policy Engine routing & safety rules
    6. Updates payment status, routing tier, and required signature counts
    7. Emits tamper-evident audit records
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

    # 5. Evaluate dynamic Policy Engine routing
    routing = evaluate_routing(
        db=db,
        payment=payment,
        three_way_facts=three_way_facts,
        risk_score=float(ml_result["risk_score"]),
    )

    # 6. Persist ML assessment and policy routing decisions
    payment.fraud_probability = ml_result["fraud_probability"]
    payment.risk_score = ml_result["risk_score"]
    payment.risk_reasons = json.dumps(ml_result["reasons"])
    payment.routing_tier = routing.routing_tier
    payment.required_signatures = routing.required_signatures
    payment.status = routing.status

    db.commit()
    db.refresh(payment)

    # 7. Audit log the scoring and routing event
    log_event(
        db=db,
        user_id="trustguard_scoring_orchestrator",
        action="PAYMENT_SCORED",
        result="SUCCESS",
        request_id=payment.request_id,
        details={
            "risk_score": ml_result["risk_score"],
            "fraud_probability": ml_result["fraud_probability"],
            "routing_tier": routing.routing_tier,
            "status": routing.status,
            "required_signatures": routing.required_signatures,
            "escalation_reasons": routing.escalation_reasons,
            "policy_version": routing.policy_version,
        },
    )

    return PaymentScoreResponse(
        request_id=payment.request_id,
        payment_status=payment.status,
        business_checks=BusinessChecksResponse(**three_way_facts),
        ml_assessment=MLAssessmentResponse(**ml_result),
        routing=routing,
        features_used=features,
    )
