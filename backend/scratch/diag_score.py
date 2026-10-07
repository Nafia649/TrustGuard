import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard")
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
from app.services.feature_builder import build_ml_features
from app.services.ml_client import MLClient

def diagnose():
    db = SessionLocal()
    payment = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == "INV-DEMO-005").order_by(PaymentRequest.timestamp.desc()).first()
    if not payment:
        print("Payment not found.")
        return

    print("Building features...")
    features = build_ml_features(db, payment)
    print("\n--- 4. EXACT 17 FEATURES ---")
    for k, v in features.items():
        print(f"{k}: {v} (Type: {type(v).__name__})")
        
    print("\n--- INVOCING XGBOOST ---")
    xgb = MLClient()
    result = xgb.predict_risk(features)
    
    print("\n--- 1. RAW FRAUD PROBABILITY ---")
    print(result.get("fraud_probability_raw", result.get("fraud_probability")))
    
    print("\n--- 2. FINAL RISK SCORE ---")
    print(result.get("risk_score"))
    
    print("\n--- 5. SHAP REASONS ---")
    print(json.dumps(result.get("risk_reasons", []), indent=2))
    
    # Check policy routing based on 68,000 amount
    from app.services.policy_engine import evaluate_policy
    routing = evaluate_policy(db, payment.request_id, result.get("risk_score"), result.get("risk_reasons", []))
    print("\n--- 3. ROUTING TIER ---")
    print(routing.tier)
    print("\n--- 9. POLICY AFFECTED BY 68,000 AMOUNT? ---")
    print("Policy rules checked during evaluate_policy:")
    from app.models.policy import PolicyConfig
    policy = db.query(PolicyConfig).filter(PolicyConfig.active == True).first()
    print(f"Auto-approve cap: {policy.auto_approve_cap_amount}")
    if payment.amount > policy.auto_approve_cap_amount:
        print(f"Yes. Amount {payment.amount} > {policy.auto_approve_cap_amount}, routing to TWO_SIGNATURES or HOLD.")
    else:
        print(f"No. Amount {payment.amount} <= {policy.auto_approve_cap_amount}.")

if __name__ == "__main__":
    diagnose()
