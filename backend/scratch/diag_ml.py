import sys
import json
sys.path.insert(0, r"C:\Users\USER\TrustGuard\backend")
sys.path.insert(0, r"C:\Users\USER\TrustGuard")
from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
from app.services.feature_builder import build_ml_features
from ml.src.predict import predict_risk as ml_predict

def diagnose():
    db = SessionLocal()
    payment = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == "INV-DEMO-005").order_by(PaymentRequest.timestamp.desc()).first()
    if not payment:
        print("Payment not found.")
        return

    features = build_ml_features(db, payment)
    result = ml_predict(features)
    print("--- ML OUTPUT ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    diagnose()
