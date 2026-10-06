"""
TrustGuard — XGBoost Fraud Detection Model Training

Trains an XGBClassifier on the prepared synthetic dataset.
Handles class imbalance via scale_pos_weight.
Outputs fraud_probability (0-1) and risk_score (0-100).
Saves the trained model to ml/models/trustguard_xgb.json.
"""

import os
import sys
import xgboost as xgb
import pandas as pd
import numpy as np

# Import from feature_engineering module
from feature_engineering import load_feature_names, load_dataset, prepare_features, split_data

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(SCRIPT_DIR)

DATA_PATH = os.path.join(ML_DIR, "data", "training_data.csv")
CONTRACT_PATH = os.path.join(ML_DIR, "feature_names.json")
MODEL_PATH = os.path.join(ML_DIR, "models", "trustguard_xgb.json")

def train_model():
    print("=" * 60)
    print("  TrustGuard — Model Training Phase")
    print("=" * 60)
    
    # 1. Load pipeline and prep data
    feature_names = load_feature_names(CONTRACT_PATH)
    df = load_dataset(DATA_PATH)
    X, y = prepare_features(df, feature_names)
    
    # 2. Split data (stratified)
    X_train, X_test, y_train, y_test = split_data(X, y)
    print(f"Training set: {X_train.shape[0]} records")
    print(f"Test set:     {X_test.shape[0]} records")
    
    # 3. Handle class imbalance
    num_genuine = (y_train == 0).sum()
    num_fraud = (y_train == 1).sum()
    scale_pos_weight = num_genuine / num_fraud
    print(f"\nClass imbalance handling:")
    print(f"  Genuine records: {num_genuine}")
    print(f"  Fraud records:   {num_fraud}")
    print(f"  scale_pos_weight = {scale_pos_weight:.2f}")
    
    # 4. Configure XGBoost
    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos_weight,
        "random_state": 42
    }
    
    print("\nModel hyperparameters:")
    for k, v in params.items():
        print(f"  {k}: {v}")
        
    model = xgb.XGBClassifier(**params)
    
    # 5. Train
    print("\nTraining XGBoost model...")
    model.fit(X_train, y_train)
    
    # 6. Save model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    model.save_model(MODEL_PATH)
    print(f"Model saved to: {MODEL_PATH}")
    
    return model, X_test, y_test, feature_names

def validate_model(model, X_test, y_test, feature_names):
    print("\n" + "=" * 60)
    print("  Model Validation & Evaluation Setup")
    print("=" * 60)
    
    # Reload test
    print("Testing model reload...")
    loaded_model = xgb.XGBClassifier()
    loaded_model.load_model(MODEL_PATH)
    print("  Reload successful.")
    
    # Generate predictions
    print("\nGenerating test-set predictions...")
    probs = loaded_model.predict_proba(X_test)
    fraud_probability = probs[:, 1]
    risk_score = fraud_probability * 100
    
    # Basic bounds checking
    print("\nValidating prediction bounds:")
    prob_min, prob_max = fraud_probability.min(), fraud_probability.max()
    risk_min, risk_max = risk_score.min(), risk_score.max()
    print(f"  Fraud probability range: [{prob_min:.4f}, {prob_max:.4f}]")
    print(f"  Risk score range:        [{risk_min:.2f}, {risk_max:.2f}]")
    
    assert 0.0 <= prob_min <= prob_max <= 1.0, "Probability outside bounds"
    assert 0.0 <= risk_min <= risk_max <= 100.0, "Risk score outside bounds"
    assert len(fraud_probability) == len(X_test), "Count mismatch"
    print("  Bounds and counts checks passed.")
    
    # Exact feature order check
    saved_features = loaded_model.feature_names_in_
    assert list(saved_features) == feature_names, "Feature order mismatch"
    print("  Feature order perfectly maintained.")
    
    print("\nExample Predictions (Test Set):")
    
    test_results = pd.DataFrame({
        'actual_is_fraud': y_test,
        'fraud_probability': fraud_probability,
        'risk_score': risk_score
    })
    
    examples = pd.concat([
        test_results[test_results['actual_is_fraud'] == 1].head(3),
        test_results[test_results['actual_is_fraud'] == 0].head(2)
    ]).sample(frac=1, random_state=42) 
    
    print(examples.round(4).to_string(index=False))

if __name__ == "__main__":
    trained_model, X_test, y_test, fnames = train_model()
    validate_model(trained_model, X_test, y_test, fnames)
