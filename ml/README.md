# TrustGuard — ML Fraud Detection Component

## Purpose

The ML component estimates the probability that a payment transaction is fraudulent.
It provides a **fraud probability**, a **risk score**, and **human-readable explanations**
so that the backend policy engine can make the final payment decision.

> **ML is advisory only.** The model never approves, rejects, authorizes, signs, or blocks a payment.

## Technology

| Tool | Role |
|------|------|
| **XGBoost** (`XGBClassifier`) | Binary classification model for fraud detection |
| **SHAP** | Explains individual predictions with feature-level contributions |
| **Pandas / NumPy** | Data manipulation and feature engineering |
| **Scikit-learn** | Evaluation metrics, train/test splitting |

## Input Feature Contract

The model accepts exactly **17 input features** defined in [`feature_names.json`](feature_names.json):

| # | Feature | Type | Description |
|---|---------|------|-------------|
| 1 | `po_exists` | binary | Purchase order exists for this invoice |
| 2 | `po_approved` | binary | Purchase order has been approved |
| 3 | `grn_exists` | binary | Goods received note exists |
| 4 | `vendor_approved` | binary | Vendor is on the approved vendor list |
| 5 | `invoice_po_amount_ratio` | float | Invoice amount ÷ PO amount (1.0 = exact match) |
| 6 | `duplicate_invoice` | binary | Invoice number has been seen before |
| 7 | `bank_account_changed` | binary | Vendor bank account was recently changed |
| 8 | `new_vendor` | binary | Vendor was registered recently |
| 9 | `vendor_age_days` | int | Days since vendor registration |
| 10 | `past_genuine_payments` | int | Count of previous non-fraudulent payments to this vendor |
| 11 | `amount_vs_vendor_avg` | float | Transaction amount ÷ vendor's historical average |
| 12 | `unusual_time` | binary | Payment submitted outside normal business hours |
| 13 | `suspicious_channel` | binary | Payment submitted via unusual communication channel |
| 14 | `payments_last_24h` | int | Number of payments submitted in the last 24 hours |
| 15 | `amount_last_24h` | float | Total payment amount in the last 24 hours |
| 16 | `possible_split_payment` | binary | Transaction appears to be a split payment |
| 17 | `document_quality_score` | float | Quality/completeness score of supporting documents (0–1) |

### What is NOT an input feature

| Field | Role | Why excluded |
|-------|------|--------------|
| `is_fraud` | **Training target** | Label the model learns to predict (0 = genuine, 1 = fraud) |
| `fraud_probability` | **Model output** | Predicted probability of fraud |
| `risk_score` | **Derived output** | `fraud_probability × 100` |
| `shap_values` / `shap_reasons` | **Explanation output** | Generated after prediction |
| `approval_decision` / `routing_decision` | **Policy output** | Decided by the backend, not the model |

## Model Output Contract

For each transaction, the ML component returns:

```json
{
    "fraud_probability": 0.68,
    "risk_score": 68,
    "reasons": [
        "Bank account was recently changed",
        "Invoice amount is significantly higher than the purchase order",
        "Vendor is newly registered"
    ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `fraud_probability` | float (0–1) | Raw model probability of fraud |
| `risk_score` | int (0–100) | `round(fraud_probability × 100)` |
| `reasons` | list of strings | Top 3 SHAP-based human-readable explanations |

## Separation from Backend

The backend policy engine uses the ML output to decide routing:

```
ML Output (advisory)          Backend Decision (authoritative)
─────────────────────         ────────────────────────────────
fraud_probability             → auto approve
risk_score                    → one-signature approval
reasons                       → two-signature approval
                              → analyst hold
                              → escalation
```

The ML component has **no knowledge of** and **no influence over** these policy decisions.

## Planned ML Pipeline

```
Synthetic Dataset
      ↓
Feature Engineering
      ↓
XGBoost Training
      ↓
Fraud Probability
      ↓
Risk Score (0–100)
      ↓
SHAP Explanation
      ↓
Top 3 Reasons
      ↓
Backend Integration
```

## Synthetic Dataset

### Overview

| Property | Value |
|----------|-------|
| **Total records** | 8,000 |
| **Genuine records** | 7,680 (96%) |
| **Fraud records** | 320 (4%) |
| **Target column** | `is_fraud` (0 = genuine, 1 = fraud) |
| **Input features** | 17 (see feature contract above) |
| **Random seed** | 42 (fully reproducible) |
| **Output file** | `ml/data/training_data.csv` |

### Fraud Scenarios

The dataset represents 8 realistic fraud patterns (40 records each):

| # | Scenario | Key Feature Signals |
|---|----------|-------------------|
| 1 | **Fake invoice / missing PO** | `po_exists=0`, `po_approved=0`, `grn_exists≈0`, low `document_quality_score` |
| 2 | **Changed bank account** | `bank_account_changed=1`, elevated `amount_vs_vendor_avg`, sometimes `unusual_time=1` |
| 3 | **Inflated invoice** | `invoice_po_amount_ratio` significantly > 1.0 (1.3–3.5), PO exists |
| 4 | **Duplicate invoice** | `duplicate_invoice=1`, lower `document_quality_score` |
| 5 | **Split payments** | `possible_split_payment=1`, elevated `payments_last_24h` (4–15), high `amount_last_24h` |
| 6 | **Unusual payment timing** | `unusual_time=1`, often `suspicious_channel=1`, lower `document_quality_score` |
| 7 | **Suspicious channel** | `suspicious_channel=1`, often `unusual_time=1`, sometimes `new_vendor=1` |
| 8 | **New vendor + large payment** | `new_vendor=1`, `vendor_age_days` < 30, `amount_vs_vendor_avg` > 2.0, few `past_genuine_payments` |

**Design notes:**
- Fraud records have a slightly elevated base rate of various risk flags (not just the primary signal), so the model must learn *combinations* of features.
- Genuine records occasionally have isolated flags (e.g. a legitimate bank change or overtime payment), preventing the model from overfitting on any single feature.
- No single feature perfectly predicts fraud — this is by design.

### Generation Command

```bash
py ml/src/generate_data.py
```

This produces `ml/data/training_data.csv`. The script automatically validates the output.

### Reproducibility

The dataset is fully reproducible: running the generator with the same code and `RANDOM_SEED = 42` always produces identical output.

## Model Architecture & Training

The ML component trains an **XGBoost Classifier** (`xgboost.XGBClassifier`) to predict the likelihood of a payment being fraudulent (`is_fraud`).

### Hyperparameters & Class Imbalance

Fraud is inherently rare (4% in the synthetic dataset). Instead of relying on data upsampling like SMOTE, we instruct the model to pay proportional attention to the minority class by setting `scale_pos_weight`:

*   `scale_pos_weight` = (Genuine Training Records) / (Fraud Training Records)
*   Configured dynamically (e.g., 6144 / 256 = **24.0**)

**Initial Model Configuration:**
*   `objective`: `"binary:logistic"`
*   `eval_metric`: `"logloss"`
*   `n_estimators`: 300
*   `max_depth`: 6
*   `learning_rate`: 0.05
*   `subsample`: 0.8
*   `colsample_bytree`: 0.8
*   `random_state`: 42

### Outputs

The trained pipeline outputs two continuous risk indicators:

1.  **`fraud_probability`**: Raw unrounded probability derived directly from `model.predict_proba()[:, 1]`. Bound between `0.0` and `1.0`.
2.  **`risk_score`**: A scaled integer approximation mapping `fraud_probability * 100`. Bound between `0` and `100`.

### Architectural Rule: ML is Advisory Only

The XGBoost model **ONLY predicts the probability of fraud.**
It **DOES NOT**:
- Approve or reject payments
- Authorize transactions
- Decide routing or required signatures
- Place items on manual hold

All policy enforcement, thresholds, and final payment actions belong strictly to the **Backend Policy Engine**.

### Artifact Storage

The trained model is exported natively and saved as:
`ml/models/trustguard_xgb.json`

During evaluation and future prediction, the model strictly enforces the exact 17-feature order detailed in `ml/feature_names.json`.

## Evaluation

The model was evaluated strictly on the untouched test set (1,600 records) using a default decision threshold of `0.5`.

### Primary Metrics

| Metric | Score | Context |
|---|---|---|
| **Precision** | `0.9846` | When the model flags fraud, it is correct 98.46% of the time. |
| **Recall** | `1.0000` | The model caught 100% of the actual fraud cases. |
| **F1-Score** | `0.9922` | Harmonic mean of Precision and Recall. |
| **PR-AUC** | `1.0000` | Area under Precision-Recall Curve. With a fraud baseline of only `0.04` (4%), achieving 1.00 represents perfect separation across all thresholds. |
| **Accuracy** | `0.9994` | Included for completeness, though secondary to PR-AUC in imbalanced datasets. |

*Why PR-AUC matters:* Because our dataset is heavily imbalanced (4% fraud), standard ROC-AUC can be misleadingly high (due to many True Negatives). PR-AUC focuses specifically on the minority positive class. Achieving a near 1.0 PR-AUC compared to the 0.04 baseline indicates the model learned the explicit fraud scenario definitions exceptionally well.

### Confusion Matrix (Threshold = 0.5)

| | Predicted Genuine (0) | Predicted Fraud (1) |
|---|---|---|
| **Actual Genuine (0)** | **1535** (TN) | **1** (FP) |
| **Actual Fraud (1)** | **0** (FN) | **64** (TP) |

### Probability Confidence Analysis

The model exhibits extreme confidence in its predictions:
- **95.2%** of predictions have a fraud probability `< 0.01`
- **3.6%** of predictions have a fraud probability `> 0.99`

**Investigation Conclusion:** 
This high confidence is not due to target leakage. Rather, because the synthetic dataset uses distinct, hard-coded boundaries to generate fraud scenarios (e.g., `fake_invoice` explicitly sets `po_exists=0`), XGBoost's decision trees can effortlessly map these discrete rules, resulting in near-perfect linear/tree separability that lacks the ambient noise of real-world messy data.

## SHAP Fraud Explanations

Because TrustGuard's ML component is strictly advisory, its outputs must be explainable to backend operators and analysts. To accomplish this, we integrated **SHAP (SHapley Additive exPlanations)**.

### Local Explainability

Instead of providing a generic "global feature importance," the model calculates SHAP values uniquely for **every individual transaction**. This allows the system to determine exactly *why* a specific payment was flagged, based on the specific circumstances of that request.

### Top 3 Contributor Extraction

The explanation logic (`ml/src/explain.py`) processes the SHAP output dynamically:
1. Calculates the SHAP log-odds contribution for all 17 features.
2. Identifies the **direction** of the impact:
   - Positive SHAP value = increases risk.
   - Negative SHAP value = reduces risk.
3. Sorts features by their **absolute magnitude** (highest impact first).
4. Selects the top 3 strongest contributors for that specific prediction.
5. Maps the technical feature names to human-readable text via `HUMAN_MAPPING`.

### Human-Readable Mapping Example

The raw feature `invoice_po_amount_ratio` with a high positive SHAP value dynamically translates to:
> "Invoice amount differs significantly from the purchase order amount, increasing fraud risk."

The raw feature `document_quality_score` with a negative SHAP value translates to:
> "Payment document quality is normal, reducing fraud risk."

This ensures the frontend or analyst receives context-aware, readable explanations without needing to parse Python dictionaries or tree splits.

## Prediction Interface

The final integration point for the Backend Policy Engine is the `predict_risk(features)` function located in `ml/src/predict.py`. This function serves as a complete abstraction over the XGBoost and SHAP layers.

### Expected Input

The function accepts a single dictionary of features mapping to numeric values.

**Validation Rules:**
- **Strict Contract:** Must contain exactly the 17 features defined in `ml/feature_names.json`.
- **No Missing Values:** Raises a `ValueError` if required features are absent.
- **No Extra Values:** Raises a `ValueError` if unexpected features are supplied.
- **No Data Leakage:** Immediately rejects inputs containing target variables or outcome metrics (e.g., `is_fraud`, `risk_score`).
- **Data Types:** All feature values must cast cleanly to `float`.

### Output Format

The function returns a consistent dictionary combining the model's raw probability, derived risk score, and the SHAP-powered top 3 explanations.

```json
{
  "fraud_probability": 0.9997,
  "risk_score": 99.97,
  "reasons": [
    "Vendor has an unusually high number of payments in the last 24 hours, increasing fraud risk.",
    "Vendor has limited history of genuine payments, increasing fraud risk.",
    "Payment document quality is normal, reducing fraud risk."
  ]
}
```

### Backend Integration Expectations

The ML system is built to act purely as an intelligence signal. The returned `risk_score` and `reasons` are intended for frontend display and backend routing logic.

**CRITICAL:** The prediction interface **does not authorize transactions**. The Backend Policy Engine must interpret the `risk_score` (e.g., `score > 80` = Manual Hold) and execute the actual TrustGuard business logic and REALKEY signature requests.

## Backend Integration Boundary

The ML component has finalized its interface in Phase 7. The backend integration point is exposed via a clean Python module import:

```python
from ml.src.predict import predict_risk

# Pass the 17 features as a dictionary to receive the risk assessment
assessment = predict_risk(backend_features_dict)
```

### Feature Derivation Gap

Currently, the `backend/` directory is essentially empty and has no internal representation of payment requests or three-way matches. Therefore, **all 17 ML features represent an integration gap.**

The Backend Policy Engine is responsible for deriving the following 17 features and delivering them to `predict_risk()`:

1. `po_exists` (0/1 int)
2. `po_approved` (0/1 int)
3. `grn_exists` (0/1 int)
4. `vendor_approved` (0/1 int)
5. `invoice_po_amount_ratio` (float)
6. `duplicate_invoice` (0/1 int)
7. `bank_account_changed` (0/1 int)
8. `new_vendor` (0/1 int)
9. `vendor_age_days` (float/int)
10. `past_genuine_payments` (float/int)
11. `amount_vs_vendor_avg` (float)
12. `unusual_time` (0/1 int)
13. `suspicious_channel` (0/1 int)
14. `payments_last_24h` (float/int)
15. `amount_last_24h` (float)
16. `possible_split_payment` (0/1 int)
17. `document_quality_score` (float)

**Important Constraints for Backend Team:**
*   **Do not send missing features.** The ML interface will refuse to silently fill missing fields with defaults. All 17 features are mandatory.
*   **Do not send extra features.** The interface strictly validates input bounds to prevent data leakage and unexpected edge cases.
*   **Do not invent data.** If a feature is not yet fully implemented in the backend (e.g., `document_quality_score`), the backend must derive a reasonable placeholder explicitly on its side, not by altering the ML contract.

### Architectural Boundary Checklist

*   [x] **Advisory Only**: The ML model provides `fraud_probability`, `risk_score`, and `reasons`. It does **not** make decisions.
*   [x] **Policy Engine Responsibility**: The backend must take the `risk_score`, run it against thresholds, and determine if an automated approval, manual hold, or REALKEY signature is required.
*   [x] **No Internal REST Wrapping**: To keep dependencies lightweight, `predict_risk` is exposed natively. The Backend team can wrap this inside their own FastAPI route if client-side polling is required.

## Directory Structure

```
ml/
├── data/
│   └── training_data.csv  # Generated synthetic dataset (8,000 records)
├── models/                # Saved trained model artifacts
├── notebooks/             # Exploratory analysis (optional)
├── src/
│   └── generate_data.py   # Synthetic data generator
├── feature_names.json     # Canonical input feature contract
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## Setup

```bash
py -m pip install -r requirements.txt
```