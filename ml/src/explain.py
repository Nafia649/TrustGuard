"""
TrustGuard — SHAP Fraud Explanations

Integrates SHAP (SHapley Additive exPlanations) to explain the XGBoost model's
predictions on an individual transaction basis. Extracts the top 3 contributing
features and maps them to human-readable explanations based on risk direction.
"""

import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
import shap

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(SCRIPT_DIR)
MODEL_PATH = os.path.join(ML_DIR, "models", "trustguard_xgb.json")
CONTRACT_PATH = os.path.join(ML_DIR, "feature_names.json")
DATA_PATH = os.path.join(ML_DIR, "data", "training_data.csv")

# State (lazy loaded)
_model = None
_explainer = None
_feature_names = None

# Human-readable mapping for features, split by direction of impact
HUMAN_MAPPING = {
    "po_exists": {
        "increases_risk": "No purchase order exists, increasing fraud risk.",
        "reduces_risk": "Purchase order exists, reducing fraud risk."
    },
    "po_approved": {
        "increases_risk": "Purchase order is not approved, increasing fraud risk.",
        "reduces_risk": "Purchase order is approved, reducing fraud risk."
    },
    "grn_exists": {
        "increases_risk": "No goods receipt exists, increasing fraud risk.",
        "reduces_risk": "Goods receipt exists, reducing fraud risk."
    },
    "vendor_approved": {
        "increases_risk": "Vendor is not approved, increasing fraud risk.",
        "reduces_risk": "Vendor is approved, reducing fraud risk."
    },
    "invoice_po_amount_ratio": {
        "increases_risk": "Invoice amount differs significantly from the purchase order amount, increasing fraud risk.",
        "reduces_risk": "Invoice amount closely matches purchase order amount, reducing fraud risk."
    },
    "duplicate_invoice": {
        "increases_risk": "Invoice appears to be a duplicate, increasing fraud risk.",
        "reduces_risk": "No duplicate invoice detected, reducing fraud risk."
    },
    "bank_account_changed": {
        "increases_risk": "Vendor bank account was recently changed, increasing fraud risk.",
        "reduces_risk": "Vendor bank account has not changed recently, reducing fraud risk."
    },
    "new_vendor": {
        "increases_risk": "Vendor is newly registered, increasing fraud risk.",
        "reduces_risk": "Vendor is established, reducing fraud risk."
    },
    "vendor_age_days": {
        "increases_risk": "Vendor has a very short operating history, increasing fraud risk.",
        "reduces_risk": "Vendor has a longer operating history, reducing fraud risk."
    },
    "past_genuine_payments": {
        "increases_risk": "Vendor has limited history of genuine payments, increasing fraud risk.",
        "reduces_risk": "Vendor has a strong history of genuine payments, reducing fraud risk."
    },
    "amount_vs_vendor_avg": {
        "increases_risk": "Payment amount is unusually high compared with the vendor's normal payments, increasing fraud risk.",
        "reduces_risk": "Payment amount is consistent with the vendor's normal payments, reducing fraud risk."
    },
    "unusual_time": {
        "increases_risk": "Payment is being made at an unusual time, increasing fraud risk.",
        "reduces_risk": "Payment is being made during normal business hours, reducing fraud risk."
    },
    "suspicious_channel": {
        "increases_risk": "Payment request uses a suspicious communication channel, increasing fraud risk.",
        "reduces_risk": "Payment request uses a standard communication channel, reducing fraud risk."
    },
    "payments_last_24h": {
        "increases_risk": "Vendor has an unusually high number of payments in the last 24 hours, increasing fraud risk.",
        "reduces_risk": "Normal payment frequency for vendor in the last 24 hours, reducing fraud risk."
    },
    "amount_last_24h": {
        "increases_risk": "Vendor has an unusually high payment total in the last 24 hours, increasing fraud risk.",
        "reduces_risk": "Normal payment totals for vendor in the last 24 hours, reducing fraud risk."
    },
    "possible_split_payment": {
        "increases_risk": "Payment pattern suggests possible payment splitting, increasing fraud risk.",
        "reduces_risk": "No split payment pattern detected, reducing fraud risk."
    },
    "document_quality_score": {
        "increases_risk": "Payment document quality is unusually low, increasing fraud risk.",
        "reduces_risk": "Payment document quality is normal, reducing fraud risk."
    }
}

def _initialize():
    """Lazily load the model and explainer to avoid overhead on import."""
    global _model, _explainer, _feature_names
    import json
    if _model is None:
        with open(CONTRACT_PATH, "r") as f:
            _feature_names = json.load(f)
        
        _model = xgb.XGBClassifier()
        _model.load_model(MODEL_PATH)
        
        # Patch for SHAP / XGBoost 3.x compatibility
        import shap.explainers._tree as shap_tree
        if hasattr(shap_tree, "decode_ubjson_buffer") and not getattr(shap_tree, "_trustguard_patched", False):
            original_decode = shap_tree.decode_ubjson_buffer
            def patched_decode(*args, **kwargs):
                jmodel = original_decode(*args, **kwargs)
                base_score = jmodel.get("learner", {}).get("learner_model_param", {}).get("base_score")
                if isinstance(base_score, str) and base_score.startswith("[") and base_score.endswith("]"):
                    jmodel["learner"]["learner_model_param"]["base_score"] = base_score[1:-1]
                return jmodel
            shap_tree.decode_ubjson_buffer = patched_decode
            shap_tree._trustguard_patched = True
            
        # Create tree explainer specifically for XGBoost
        _explainer = shap.TreeExplainer(_model)

def explain_prediction(features_df):
    """
    Explain a single prediction using SHAP.
    
    Args:
        features_df (pd.DataFrame): DataFrame containing the required 17 features.
            If multiple rows, only the first row is explained.
            
    Returns:
        dict: The fraud probability, risk score, and top 3 human-readable reasons.
    """
    _initialize()
    
    # Ensure correct order and handle missing
    missing = [f for f in _feature_names if f not in features_df.columns]
    if missing:
        raise ValueError(f"Missing required features: {missing}")
        
    # Enforce exact feature order and extract just the first row
    X_instance = features_df[_feature_names].iloc[[0]].copy()
    
    # Calculate prediction probability
    prob = _model.predict_proba(X_instance)[0, 1]
    risk_score = int(round(prob * 100))
    
    # Calculate SHAP values (log-odds space)
    shap_values = _explainer.shap_values(X_instance)
    
    # Handle SHAP output shapes
    if isinstance(shap_values, list):
        sv = shap_values[1][0]
    else:
        # Binary xgboost tree explainer returns shape (1, n_features)
        sv = shap_values[0]
        
    # Pair features with their SHAP values
    feature_contributions = []
    for i, feature in enumerate(_feature_names):
        val = float(sv[i])
        feature_contributions.append((feature, val))
        
    # Sort by absolute magnitude (highest impact first, positive or negative)
    feature_contributions.sort(key=lambda x: abs(x[1]), reverse=True)
    
    # Take top 3
    top_3 = feature_contributions[:3]
    
    reasons = []
    for feature, val in top_3:
        # Positive SHAP value pushes towards Class 1 (Fraud)
        impact = "increases_risk" if val > 0 else "reduces_risk"
        
        # Fetch human-readable mapping
        reason_text = HUMAN_MAPPING.get(feature, {}).get(
            impact, 
            f"{feature} {'increases' if impact == 'increases_risk' else 'reduces'} fraud risk."
        )
        
        reasons.append({
            "feature": feature,
            "impact": impact,
            "shap_value": val,
            "reason": reason_text
        })
        
    return {
        "fraud_probability": float(prob),
        "risk_score": risk_score,
        "reasons": reasons
    }
    
def test_explanations():
    print("=" * 60)
    print("  TrustGuard — SHAP Explanations Testing")
    print("=" * 60)
    
    # Load dataset to grab test cases
    df = pd.read_csv(DATA_PATH)
    
    tests = []
    # 1. Genuine
    tests.append(("1. Genuine", df[df['is_fraud'] == 0].iloc[[0]]))
    
    # 2. Fraudulent
    tests.append(("2. Fraudulent", df[df['is_fraud'] == 1].iloc[[0]]))
    
    # 3. Changed bank account
    tests.append(("3. Changed Bank Account (Fraud)", df[(df['is_fraud'] == 1) & (df['bank_account_changed'] == 1)].iloc[[0]]))
    
    # 4. Inflated invoice
    tests.append(("4. Inflated Invoice (Fraud)", df[(df['is_fraud'] == 1) & (df['invoice_po_amount_ratio'] > 1.3)].iloc[[0]]))
    
    # 5. New vendor
    tests.append(("5. New Vendor (Fraud)", df[(df['is_fraud'] == 1) & (df['new_vendor'] == 1)].iloc[[0]]))
    
    for name, row in tests:
        print("\n" + "="*50)
        print(f" TEST CASE: {name}")
        print("="*50)
        
        res = explain_prediction(row)
        
        prob = res['fraud_probability']
        pred = "FRAUD" if prob >= 0.5 else "GENUINE"
        print(f"Prediction:        {pred}")
        print(f"Fraud Probability: {prob:.4f}")
        print(f"Risk Score:        {res['risk_score']:.2f}")
        
        print("\nTop 3 SHAP Reasons:")
        for i, r in enumerate(res['reasons'], 1):
            impact_symbol = "[+]" if r['impact'] == "increases_risk" else "[-]"
            print(f"  {i}. {r['feature']} (SHAP: {r['shap_value']:>7.4f}) {impact_symbol}")
            print(f"     -> {r['reason']}")
            
if __name__ == "__main__":
    test_explanations()
