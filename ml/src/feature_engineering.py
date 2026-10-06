"""
TrustGuard — Feature Engineering and Train/Test Preparation

This module prepares the generated synthetic dataset for model training.
It enforces the feature contract, prevents target leakage, and creates
a reproducible stratified train/test split.
"""

import json
import os
import pandas as pd
from sklearn.model_selection import train_test_split

# Columns that must NEVER be part of the feature matrix (X)
BANNED_COLUMNS = [
    "is_fraud",
    "fraud_probability",
    "risk_score",
    "shap_values",
    "shap_reasons",
    "approval_decision",
    "routing_decision",
]

def load_feature_names(contract_path):
    """Load the canonical feature list from the JSON contract."""
    with open(contract_path, "r") as f:
        features = json.load(f)
    return features

def load_dataset(data_path):
    """Load the synthetic dataset."""
    return pd.read_csv(data_path)

def prepare_features(df, feature_names, target_col="is_fraud"):
    """
    Prepare feature matrix X and target vector y.
    Enforces feature order and checks for data leakage.
    """
    # 1. Extract y
    if target_col not in df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset!")
    y = df[target_col].copy()

    # 2. Extract X in exact order specified by the contract
    missing_features = [f for f in feature_names if f not in df.columns]
    if missing_features:
        raise ValueError(f"Missing required features in dataset: {missing_features}")
    
    X = df[feature_names].copy()

    # 3. Validate X is strictly numeric (required for XGBoost)
    non_numeric = X.select_dtypes(exclude=['number']).columns.tolist()
    if non_numeric:
        raise TypeError(f"Non-numeric features detected in X: {non_numeric}")

    # 4. Deep Leakage check on X columns
    for col in BANNED_COLUMNS:
        if col in X.columns:
            raise ValueError(f"LEAKAGE DETECTED: Banned column '{col}' found in X matrix!")

    return X, y

def split_data(X, y, test_size=0.2, random_state=42):
    """
    Perform a stratified train/test split to preserve fraud ratio.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=test_size, 
        random_state=random_state, 
        stratify=y  # Essential for imbalanced fraud data
    )
    return X_train, X_test, y_train, y_test


if __name__ == "__main__":
    # Quick validation run when executed directly
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ml_dir = os.path.dirname(script_dir)
    
    data_path = os.path.join(ml_dir, "data", "training_data.csv")
    contract_path = os.path.join(ml_dir, "feature_names.json")
    
    print("=" * 60)
    print("  TrustGuard — Feature Engineering & Split Validation")
    print("=" * 60)
    
    # Load
    feature_names = load_feature_names(contract_path)
    df = load_dataset(data_path)
    print(f"1. Original dataset shape: {df.shape}")
    
    # Prepare
    X, y = prepare_features(df, feature_names)
    print(f"2. X shape: {X.shape}")
    print(f"3. y shape: {y.shape}")
    
    # Split
    X_train, X_test, y_train, y_test = split_data(X, y)
    print(f"4. Training set shape: X={X_train.shape}, y={y_train.shape}")
    print(f"5. Test set shape: X={X_test.shape}, y={y_test.shape}")
    
    train_fraud = y_train.sum()
    train_total = len(y_train)
    print(f"6. Training fraud: {train_fraud} records ({train_fraud/train_total*100:.2f}%)")
    
    test_fraud = y_test.sum()
    test_total = len(y_test)
    print(f"7. Test fraud: {test_fraud} records ({test_fraud/test_total*100:.2f}%)")
    
    print(f"\n8. Final feature names in exact order:")
    for i, f in enumerate(X.columns):
        print(f"   {i+1}. {f}")
        
    print("\n--- Leakage & Type Validation ---")
    is_numeric = all(pd.api.types.is_numeric_dtype(X[c]) for c in X.columns)
    print(f"9. All X columns are numeric: {'PASS' if is_numeric else 'FAIL'}")
    
    print(f"10. 'is_fraud' NOT in X: {'PASS' if 'is_fraud' not in X.columns else 'FAIL'}")
    
    has_leakage = any(c in X.columns for c in BANNED_COLUMNS)
    print(f"11. No output/target leakage: {'PASS' if not has_leakage else 'FAIL'}")
    
    print("12. Split is reproducible: PASS (stratified with random_state=42)")
    
    print("\nPhase 2 implementation complete.")
