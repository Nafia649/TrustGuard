"""
TrustGuard — Reusable ML Prediction Interface

Provides a clean, validated interface for backend systems to request
fraud risk predictions. It strictly enforces the feature contract,
evaluates the transaction using the saved XGBoost model, and delegates
to the SHAP explainer for human-readable top 3 reasons.
"""

import os
import json
import math
import pandas as pd

BINARY_FEATURES = {
    "po_exists", "po_approved", "grn_exists", "vendor_approved",
    "duplicate_invoice", "bank_account_changed", "new_vendor",
    "unusual_time", "suspicious_channel", "possible_split_payment"
}

CONTINUOUS_BOUNDS = {
    "document_quality_score": (0.0, 1.0),
    "invoice_po_amount_ratio": (0.0, float('inf')),
    "amount_vs_vendor_avg": (0.0, float('inf')),
    "vendor_age_days": (0.0, float('inf')),
    "past_genuine_payments": (0.0, float('inf')),
    "payments_last_24h": (0.0, float('inf')),
    "amount_last_24h": (0.0, float('inf')),
}

# Import SHAP explanation pipeline (which already loads the XGBoost model natively)
from .explain import explain_prediction

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(SCRIPT_DIR)
CONTRACT_PATH = os.path.join(ML_DIR, "feature_names.json")
DATA_PATH = os.path.join(ML_DIR, "data", "training_data.csv")

BANNED_FEATURES = {
    "is_fraud",
    "fraud_probability",
    "risk_score",
    "shap_values",
    "shap_reasons",
    "approval_decision",
    "routing_decision"
}

_feature_names = None

def _load_contract():
    global _feature_names
    if _feature_names is None:
        if not os.path.exists(CONTRACT_PATH):
            raise FileNotFoundError(f"Feature contract missing at {CONTRACT_PATH}")
        with open(CONTRACT_PATH, "r") as f:
            _feature_names = json.load(f)
    return _feature_names

def predict_risk(features: dict) -> dict:
    """
    Evaluates a single payment transaction for fraud risk.
    
    Args:
        features (dict): A dictionary mapping feature names to numeric values.
        
    Returns:
        dict: A dictionary containing:
            - fraud_probability (float, 0-1)
            - risk_score (float, 0-100)
            - reasons (list of 3 string explanations)
    """
    contract = _load_contract()
    
    # 1. BANNED FEATURE CHECK
    banned_provided = [f for f in features.keys() if f in BANNED_FEATURES]
    if banned_provided:
        raise ValueError(f"Validation Error: Banned features provided in input: {banned_provided}")
        
    # 2. MISSING FEATURE CHECK
    missing = [f for f in contract if f not in features]
    if missing:
        raise ValueError(f"Validation Error: Missing required features: {missing}")
        
    # 3. UNEXPECTED FEATURE CHECK
    extra = [f for f in features if f not in contract]
    if extra:
        raise ValueError(f"Validation Error: Unexpected extra features provided: {extra}")
        
    # 4. TYPE CHECK & BOUNDS ENFORCEMENT
    for k, v in features.items():
        try:
            value = float(v)
        except (ValueError, TypeError):
            raise TypeError(f"Validation Error: Feature '{k}' must be numeric, got {type(v).__name__}: {v}")
            
        if not math.isfinite(value):
            raise ValueError(f"Validation Error: Feature '{k}' must be finite, got {value}")
            
        if k in BINARY_FEATURES:
            if value not in (0.0, 1.0):
                raise ValueError(f"Validation Error: Binary feature '{k}' must be 0 or 1, got {value}")
                
        if k in CONTINUOUS_BOUNDS:
            min_val, max_val = CONTINUOUS_BOUNDS[k]
            if not (min_val <= value <= max_val):
                raise ValueError(f"Validation Error: Feature '{k}' must be between {min_val} and {max_val}, got {value}")
            
    # 5. ORDERING AND CONVERSION
    # Creates a 1-row DataFrame enforcing the exact contract order
    df = pd.DataFrame([features])[contract]
    df = df.apply(pd.to_numeric)
    
    # 6. MODEL INFERENCE & SHAP EXPLANATIONS
    # explain_prediction handles predict_proba() and SHAP tree extraction
    explanation_data = explain_prediction(df)
    
    # 7. FORMAT OUTPUT
    return {
        "fraud_probability": explanation_data["fraud_probability"],
        "risk_score": explanation_data["risk_score"],
        "reasons": [r["reason"] for r in explanation_data["reasons"]]
    }


def test_interface():
    print("=" * 60)
    print("  TrustGuard — Prediction Interface Testing")
    print("=" * 60)
    
    df = pd.read_csv(DATA_PATH)
    
    # ---------------------------------------------------------
    # VALID PREDICTION TESTS
    # ---------------------------------------------------------
    print("\n--- VALID TRANSACTIONS ---")
    
    test_cases = [
        ("1. Genuine Transaction", df[df['is_fraud'] == 0].iloc[0].drop('is_fraud').to_dict()),
        ("2. Fraudulent Transaction", df[df['is_fraud'] == 1].iloc[0].drop('is_fraud').to_dict()),
        ("3. Changed Bank Account", df[(df['is_fraud'] == 1) & (df['bank_account_changed'] == 1)].iloc[0].drop('is_fraud').to_dict()),
        ("4. Inflated Invoice", df[(df['is_fraud'] == 1) & (df['invoice_po_amount_ratio'] > 1.3)].iloc[0].drop('is_fraud').to_dict()),
        ("5. New Vendor + Large Payment", df[(df['is_fraud'] == 1) & (df['new_vendor'] == 1)].iloc[0].drop('is_fraud').to_dict()),
    ]
    
    for name, features_dict in test_cases:
        print(f"\n{name}")
        result = predict_risk(features_dict)
        print(json.dumps(result, indent=2))
        
    # ---------------------------------------------------------
    # INVALID PREDICTION TESTS (Error Handling)
    # ---------------------------------------------------------
    print("\n--- INVALID INPUT TESTS ---")
    
    base_dict = df[df['is_fraud'] == 0].iloc[0].drop('is_fraud').to_dict()
    
    # Test A: Missing Feature
    dict_missing = base_dict.copy()
    del dict_missing["po_exists"]
    try:
        predict_risk(dict_missing)
        print("FAIL: Missing feature test did not raise an error.")
    except Exception as e:
        print(f"Missing feature test   -> PASSED (Caught: {e})")
        
    # Test B: Extra Feature
    dict_extra = base_dict.copy()
    dict_extra["unrelated_data"] = 1.0
    try:
        predict_risk(dict_extra)
        print("FAIL: Extra feature test did not raise an error.")
    except Exception as e:
        print(f"Extra feature test     -> PASSED (Caught: {e})")
        
    # Test C: Non-numeric
    dict_str = base_dict.copy()
    dict_str["vendor_age_days"] = "thirty_days"
    try:
        predict_risk(dict_str)
        print("FAIL: Non-numeric test did not raise an error.")
    except Exception as e:
        print(f"Non-numeric test       -> PASSED (Caught: {e})")

    # Test D: Banned Output Feature
    dict_banned = base_dict.copy()
    dict_banned["is_fraud"] = 1
    try:
        predict_risk(dict_banned)
        print("FAIL: Banned feature test did not raise an error.")
    except Exception as e:
        print(f"Banned feature test    -> PASSED (Caught: {e})")
        
    # Test E: NaN Value
    dict_nan = base_dict.copy()
    dict_nan["amount_last_24h"] = "NaN"
    try:
        predict_risk(dict_nan)
        print("FAIL: NaN test did not raise an error.")
    except Exception as e:
        print(f"NaN test               -> PASSED (Caught: {e})")
        
    # Test F: Binary Bounds
    dict_binary = base_dict.copy()
    dict_binary["new_vendor"] = -50
    try:
        predict_risk(dict_binary)
        print("FAIL: Binary bounds test did not raise an error.")
    except Exception as e:
        print(f"Binary bounds test     -> PASSED (Caught: {e})")
        
    # Test G: Continuous Bounds
    dict_cont = base_dict.copy()
    dict_cont["document_quality_score"] = 500
    try:
        predict_risk(dict_cont)
        print("FAIL: Continuous bounds test did not raise an error.")
    except Exception as e:
        print(f"Continuous bounds test -> PASSED (Caught: {e})")

    print("\nTests complete.")

if __name__ == "__main__":
    test_interface()
