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