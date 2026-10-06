"""
TrustGuard ML/Backend Integration Tests

Validates that the backend can successfully interact with the ML boundary 
using the 17-feature contract.
"""

import json
from predict import predict_risk

def run_integration_test():
    print("=" * 60)
    print("  TrustGuard — Backend Integration Test")
    print("=" * 60)
    
    # Simulate the backend passing the 17 features after deriving them
    # from its PaymentRequest and Three-Way Match data.
    # Note: Binary features must be 0/1 integers.
    backend_payload = {
        "po_exists": 1,
        "po_approved": 1,
        "grn_exists": 1,
        "vendor_approved": 1,
        "invoice_po_amount_ratio": 1.0,
        "duplicate_invoice": 0,
        "bank_account_changed": 0,
        "new_vendor": 0,
        "vendor_age_days": 1200,
        "past_genuine_payments": 50,
        "amount_vs_vendor_avg": 1.05,
        "unusual_time": 0,
        "suspicious_channel": 0,
        "payments_last_24h": 1,
        "amount_last_24h": 5000.0,
        "possible_split_payment": 0,
        "document_quality_score": 0.95
    }
    
    print("\n1. Simulated Backend Payload:")
    print(json.dumps(backend_payload, indent=2))
    
    # Ensure exactly 17 features
    assert len(backend_payload) == 17, "Payload must contain exactly 17 features."
    
    try:
        # Call the integration boundary
        result = predict_risk(backend_payload)
        
        print("\n2. ML Prediction Result:")
        print(json.dumps(result, indent=2))
        
        # Verify result structure
        assert "fraud_probability" in result
        assert "risk_score" in result
        assert "reasons" in result
        
        print("\n3. Status: SUCCESS")
        print("Backend integration boundary verified successfully.")
        
    except Exception as e:
        print(f"\n3. Status: FAILED - {str(e)}")

if __name__ == "__main__":
    run_integration_test()
