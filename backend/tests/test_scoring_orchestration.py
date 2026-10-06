import json
import pytest
from app.models.payment_request import PaymentRequest
from app.services.ml_client import MLClient


def test_scoring_orchestration_low_risk_scenario(client):
    """Verify complete scoring flow for Scenario 1 (REQ-DEMO-001): low risk -> AUTO_APPROVE -> AUTHORIZED."""
    client.post("/seed")

    response = client.post("/payments/REQ-DEMO-001/score")
    assert response.status_code == 200
    data = response.json()

    # Section 40 & 25 Contract Verification
    assert data["request_id"] == "REQ-DEMO-001"
    assert data["status"] == "AUTHORIZED"
    assert data["routing_tier"] == "AUTO_APPROVE"
    assert data["required_signatures"] == 0
    assert 0 <= data["risk_score"] < 30
    assert 0.0 <= data["fraud_probability"] < 0.30
    assert isinstance(data["reasons"], list)

    # Business checks & ML assessment verification
    assert data["business_checks"]["po_exists"] == 1
    assert data["business_checks"]["po_approved"] == 1
    assert data["business_checks"]["amount_match"] is True

    # Verify database was updated and GET /payments/{id} reflects the persisted score
    get_res = client.get("/payments/REQ-DEMO-001")
    assert get_res.status_code == 200
    payment_data = get_res.json()
    assert payment_data["status"] == "AUTHORIZED"
    assert payment_data["risk_score"] == data["risk_score"]
    assert payment_data["routing_tier"] == "AUTO_APPROVE"
    assert payment_data["required_signatures"] == 0


def test_scoring_orchestration_medium_risk_scenario(client):
    """Verify complete scoring flow for Scenario 2 (REQ-DEMO-002): medium risk -> ONE_SIGNATURE -> PENDING_APPROVAL."""
    client.post("/seed")

    response = client.post("/payments/REQ-DEMO-002/score")
    assert response.status_code == 200
    data = response.json()

    assert data["request_id"] == "REQ-DEMO-002"
    assert data["status"] == "PENDING_APPROVAL"
    assert data["routing_tier"] == "ONE_SIGNATURE"
    assert data["required_signatures"] == 1
    assert data["routing"]["authorized_roles"] == ["senior_administrator"]

    # Verify persisted state
    get_res = client.get("/payments/REQ-DEMO-002")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "PENDING_APPROVAL"
    assert get_res.json()["required_signatures"] == 1


def test_scoring_orchestration_audit_event_logged(client, db_session):
    """Verify that scoring emits an immutable PAYMENT_SCORED audit record with hash chain."""
    client.post("/seed")
    client.post("/payments/REQ-DEMO-001/score")

    from app.models.audit_log import AuditLog
    from app.services.audit_service import verify_chain

    audit_entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.request_id == "REQ-DEMO-001", AuditLog.action == "PAYMENT_SCORED")
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.result == "SUCCESS"
    assert "AUTO_APPROVE" in audit_entry.details

    # Cryptographic integrity must remain valid
    verification = verify_chain(db_session)
    assert verification["valid"] is True


def test_scoring_pluggability_with_custom_ml_predictor(client, monkeypatch):
    """Verify the ML teammate can plug in a custom predict_risk implementation cleanly."""
    client.post("/seed")

    captured_features = {}

    def custom_xgboost_predictor(feats):
        captured_features.update(feats)
        return {
            "fraud_probability": 0.42,
            "risk_score": 42,
            "reasons": [
                {
                    "feature": "invoice_po_amount_ratio",
                    "impact": "medium",
                    "description": "Invoice slightly elevated",
                }
            ],
        }

    # Inject predictor into the ml_client adapter
    from app.services import ml_client as ml_module
    monkeypatch.setattr(ml_module.ml_client, "_custom_predictor", custom_xgboost_predictor)

    response = client.post("/payments/REQ-DEMO-001/score")
    assert response.status_code == 200
    data = response.json()

    # Verify custom predictor was called with exactly 17 features
    assert len(captured_features) == 17
    assert data["risk_score"] == 42
    assert data["fraud_probability"] == 0.42
    assert data["routing_tier"] == "ONE_SIGNATURE"
    assert data["status"] == "PENDING_APPROVAL"
