
import os
import sys
import json
sys.path.append('C:/Users/USER/TrustGuard')
sys.path.append('C:/Users/USER/TrustGuard/backend')

from app.database import SessionLocal
from app.models.payment_request import PaymentRequest
import ast
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
db = SessionLocal()

for i in range(11, 21):
    inv_id = f'INV-DEMO-0{i}'
    p = db.query(PaymentRequest).filter(PaymentRequest.invoice_id == inv_id).first()
    if not p:
        print(f'Missing {inv_id}')
        continue
    
    if p.status == 'PENDING':
        # Let\'s score it!
        client.post(f'/api/v1/payments/{p.request_id}/score')
        db.refresh(p)
    
    print(f'==================================================')
    print(f'Invoice ID: {inv_id}')
    print(f'Vendor: {p.vendor_id}')
    print(f'Amount: {p.amount}')
    
    print(f'Risk Score: {p.risk_score}')
    print(f'Fraud Probability: {p.fraud_probability}')
    print(f'Routing Tier: {p.routing_tier}')
    print(f'Payment Status: {p.status}')
    
    try:
        reasons = json.loads(p.risk_reasons) if p.risk_reasons else {}
        print(f'Top 3 SHAP: {list(reasons.items())[:3]}')
    except:
        print('Top 3 SHAP: []')
    
    from app.services.feature_builder import build_ml_features
    features = build_ml_features(db, p)
    print('17-Feature Vector:')
    for k, v in features.items():
        print(f'  {k}: {v}')
    print()

