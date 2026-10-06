import pytest
from datetime import datetime, timedelta
from app.models.vendor import Vendor
from app.models.purchase_order import PurchaseOrder
from app.models.goods_receipt import GoodsReceipt
from app.models.payment_request import PaymentRequest
from app.services.three_way_match import perform_three_way_match
from app.services.feature_builder import (
    build_ml_features,
    validate_feature_contract,
    MissingFeatureDerivationError,
    FeatureContractValidationError,
    REQUIRED_ML_FEATURES,
)
from app.services.ml_client import ml_client, MLClient, mock_predict_risk


def test_valid_three_way_match(client, db_session):
    """1. Test valid three-way match with matching PO, GRN, vendor, and amount."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    result = perform_three_way_match(db_session, payment)
    assert result["po_exists"] == 1
    assert result["po_approved"] == 1
    assert result["grn_exists"] == 1
    assert result["goods_received"] == 1
    assert result["vendor_approved"] == 1
    assert result["amount_match"] is True
    assert result["invoice_po_amount_ratio"] == 1.0
    assert result["duplicate_invoice"] == 0
    assert result["bank_account_match"] is True
    assert result["bank_account_changed"] == 0


def test_missing_po(client, db_session):
    """2. Test three-way match with missing PO."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-004").first()

    result = perform_three_way_match(db_session, payment)
    assert result["po_exists"] == 0
    assert result["po_approved"] == 0
    assert result["grn_exists"] == 0
    assert result["amount_match"] is False
    assert result["invoice_po_amount_ratio"] is None


def test_unapproved_po(db_session):
    """3. Test three-way match with an unapproved PO."""
    vendor = Vendor(
        vendor_id="V-TEST-UNAPP",
        vendor_name="Unapproved PO Vendor",
        approved=True,
        bank_account="BANK-UNAPP",
        onboarded_date=datetime.utcnow() - timedelta(days=100),
        usual_amount_mean=10000.0,
    )
    po = PurchaseOrder(
        po_id="PO-UNAPPROVED",
        vendor_id="V-TEST-UNAPP",
        amount=10000.0,
        status="PENDING_REVIEW",  # Not APPROVED
        date=datetime.utcnow() - timedelta(days=5),
    )
    payment = PaymentRequest(
        request_id="REQ-TEST-UNAPP-PO",
        vendor_id="V-TEST-UNAPP",
        amount=10000.0,
        currency="INR",
        bank_account="BANK-UNAPP",
        invoice_id="INV-TEST-UNAPP",
        po_id="PO-UNAPPROVED",
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([vendor, po, payment])
    db_session.commit()

    result = perform_three_way_match(db_session, payment)
    assert result["po_exists"] == 1
    assert result["po_approved"] == 0


def test_missing_grn(db_session):
    """4. Test three-way match with PO but missing GRN (goods not received)."""
    vendor = Vendor(
        vendor_id="V-TEST-NOGRN",
        vendor_name="No GRN Vendor",
        approved=True,
        bank_account="BANK-NOGRN",
        onboarded_date=datetime.utcnow() - timedelta(days=100),
        usual_amount_mean=20000.0,
    )
    po = PurchaseOrder(
        po_id="PO-NOGRN",
        vendor_id="V-TEST-NOGRN",
        amount=20000.0,
        status="APPROVED",
        date=datetime.utcnow() - timedelta(days=5),
    )
    payment = PaymentRequest(
        request_id="REQ-TEST-NOGRN",
        vendor_id="V-TEST-NOGRN",
        amount=20000.0,
        currency="INR",
        bank_account="BANK-NOGRN",
        invoice_id="INV-TEST-NOGRN",
        po_id="PO-NOGRN",
        timestamp=datetime.utcnow(),
    )
    db_session.add_all([vendor, po, payment])
    db_session.commit()

    result = perform_three_way_match(db_session, payment)
    assert result["po_exists"] == 1
    assert result["grn_exists"] == 0
    assert result["goods_received"] == 0


def test_unapproved_vendor(client, db_session):
    """5. Test three-way match with unapproved vendor."""
    client.post("/seed")
    # VEND-004 is unapproved in seed data
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-004").first()

    result = perform_three_way_match(db_session, payment)
    assert result["vendor_approved"] == 0


def test_invoice_po_amount_mismatch(client, db_session):
    """6. Test three-way match with invoice amount exceeding PO tolerance."""
    client.post("/seed")
    # PO-2026-001 is 45,000; create payment of 75,000 against it
    mismatched_payment = PaymentRequest(
        request_id="REQ-TEST-MISMATCH",
        vendor_id="VEND-001",
        amount=75000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-TEST-MISMATCH-99",
        po_id="PO-2026-001",
        timestamp=datetime.utcnow(),
    )
    db_session.add(mismatched_payment)
    db_session.commit()

    result = perform_three_way_match(db_session, mismatched_payment, tolerance_percent=2.0)
    assert result["po_exists"] == 1
    assert result["amount_match"] is False
    assert result["invoice_po_amount_ratio"] == round(75000.0 / 45000.0, 4)


def test_duplicate_invoice(client, db_session):
    """7. Test duplicate invoice detection across distinct payment requests."""
    client.post("/seed")
    # REQ-DEMO-001 has vendor VEND-001 and invoice INV-2026-001
    dup_payment = PaymentRequest(
        request_id="REQ-DUP-TEST",
        vendor_id="VEND-001",
        amount=45000.0,
        currency="INR",
        bank_account="ACME-BANK-001",
        invoice_id="INV-2026-001",  # Same invoice
        po_id="PO-2026-001",
        timestamp=datetime.utcnow(),
    )
    db_session.add(dup_payment)
    db_session.commit()

    result = perform_three_way_match(db_session, dup_payment)
    assert result["duplicate_invoice"] == 1


def test_bank_account_mismatch_change(client, db_session):
    """8. Test bank account mismatch detection."""
    client.post("/seed")
    payment = PaymentRequest(
        request_id="REQ-TEST-BANK-CHANGE",
        vendor_id="VEND-001",
        amount=45000.0,
        currency="INR",
        bank_account="CHANGED-UNAUTHORIZED-BANK-999",  # Different from ACME-BANK-001
        invoice_id="INV-TEST-BANK-99",
        po_id="PO-2026-001",
        timestamp=datetime.utcnow(),
    )
    db_session.add(payment)
    db_session.commit()

    result = perform_three_way_match(db_session, payment)
    assert result["bank_account_match"] is False
    assert result["bank_account_changed"] == 1


def test_correct_feature_construction(client, db_session):
    """9. Test that build_ml_features produces all 17 features with exact expected contract."""
    client.post("/seed")
    payment = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-001").first()

    features = build_ml_features(db_session, payment)
    assert len(features) == 17
    assert set(features.keys()) == set(REQUIRED_ML_FEATURES)

    # Validate types
    assert isinstance(features["po_exists"], int)
    assert isinstance(features["invoice_po_amount_ratio"], float)
    assert isinstance(features["vendor_age_days"], int)
    assert isinstance(features["document_quality_score"], float)


def test_missing_feature_is_rejected_rather_than_fabricated(client, db_session):
    """10. Test that missing feature derivation raises MissingFeatureDerivationError and never defaults/fabricates."""
    client.post("/seed")
    # REQ-DEMO-004 has NO PO and shadow vendor with no baseline
    payment_no_po = db_session.query(PaymentRequest).filter(PaymentRequest.request_id == "REQ-DEMO-004").first()

    with pytest.raises(MissingFeatureDerivationError) as exc_info:
        build_ml_features(db_session, payment_no_po)

    assert exc_info.value.feature_name == "invoice_po_amount_ratio"
    assert "cannot legitimately compute" in exc_info.value.reason.lower()


def test_unexpected_feature_is_rejected():
    """11. Test that unexpected features not in the 17-feature contract are strictly rejected."""
    invalid_features = {feat: 1.0 for feat in REQUIRED_ML_FEATURES}
    invalid_features["uncontracted_extra_feature"] = 999.0

    with pytest.raises(FeatureContractValidationError) as exc_info:
        validate_feature_contract(invalid_features)
    assert "unexpected" in str(exc_info.value).lower()


def test_ml_adapter_receives_exact_feature_contract():
    """12. Test that MLClient verifies the 17-feature contract before invoking model."""
    received_features = {}

    def spy_predictor(feats):
        received_features.update(feats)
        return {"fraud_probability": 0.12, "risk_score": 12, "reasons": []}

    client = MLClient(custom_predictor=spy_predictor)
    valid_features = {feat: 1 if "po" in feat or "approved" in feat else 0.5 for feat in REQUIRED_ML_FEATURES}
    # Fix binary features
    for k in ["po_exists", "po_approved", "grn_exists", "vendor_approved", "duplicate_invoice",
              "bank_account_changed", "new_vendor", "unusual_time", "suspicious_channel", "possible_split_payment"]:
        valid_features[k] = 1

    result = client.predict_risk(valid_features)
    assert len(received_features) == 17
    assert set(received_features.keys()) == set(REQUIRED_ML_FEATURES)
    assert result["risk_score"] == 12


def test_ml_result_is_returned_correctly():
    """13. Test ML mock prediction returns formatted risk score and reasons."""
    valid_features = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "invoice_po_amount_ratio": 1.0,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
        "new_vendor": 0,
        "vendor_age_days": 180,
        "past_genuine_payments": 12,
        "amount_vs_vendor_avg": 1.0,
        "unusual_time": 0,
        "suspicious_channel": 0,
        "payments_last_24h": 0,
        "amount_last_24h": 0.0,
        "possible_split_payment": 0,
        "document_quality_score": 0.95,
    }
    result = mock_predict_risk(valid_features)
    assert "fraud_probability" in result
    assert "risk_score" in result
    assert "reasons" in result
    assert isinstance(result["risk_score"], int)
    assert 0 <= result["risk_score"] <= 100


def test_ml_is_not_retrained_by_backend():
    """14. Test that the backend does not duplicate ML model training logic."""
    import inspect
    from app.services import ml_client as ml_module

    # Verify no training functions or XGBoost fitting occurs in the backend service
    source = inspect.getsource(ml_module)
    assert "fit(" not in source
    assert "train(" not in source
    assert "XGBClassifier" not in source
    assert "train_test_split" not in source


def test_api_score_endpoint_success(client):
    """Verify POST /payments/{id}/score returns business checks and ML intelligence."""
    client.post("/seed")

    response = client.post("/payments/REQ-DEMO-001/score")
    assert response.status_code == 200
    data = response.json()

    assert data["request_id"] == "REQ-DEMO-001"
    assert data["payment_status"] in ("SCORED", "AUTHORIZED")
    assert "business_checks" in data
    assert data["business_checks"]["po_exists"] == 1
    assert data["business_checks"]["amount_match"] is True

    assert "ml_assessment" in data
    assert "risk_score" in data["ml_assessment"]
    assert "fraud_probability" in data["ml_assessment"]
    assert "reasons" in data["ml_assessment"]
    assert len(data["features_used"]) == 17


def test_api_score_endpoint_missing_feature_rejected(client):
    """Verify POST /payments/{id}/score returns 422 when required feature cannot be derived legitimately."""
    client.post("/seed")

    # REQ-DEMO-004 has no PO, so invoice_po_amount_ratio cannot be derived
    response = client.post("/payments/REQ-DEMO-004/score")
    assert response.status_code == 422
    data = response.json()
    assert "invoice_po_amount_ratio" in data["detail"]["feature"]
