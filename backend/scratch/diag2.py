import sys
import json
sys.path.append('C:/Users/USER/TrustGuard/backend')

from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
from app.services.feature_builder import build_ml_features

db = SessionLocal()
for i in range(11, 21):
    inv_id = f'INV-DEMO-0{i}'
    pr = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == inv_id).order_by(PaymentRequest.timestamp.desc()).first()
    if pr:
        feats = build_ml_features(db, pr)
        print(f'{inv_id} -> {feats}')
