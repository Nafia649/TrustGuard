"""
TrustGuard — Synthetic Fraud Dataset Generator

Generates a reproducible synthetic dataset of ~8,000 payment transactions
for training the TrustGuard XGBoost fraud classifier.

Fraud scenarios represented:
  1. Fake invoice / missing PO
  2. Changed bank account
  3. Inflated invoice
  4. Duplicate invoice
  5. Split payments
  6. Unusual payment timing
  7. Suspicious communication channel
  8. New vendor + large payment

Usage:
    py ml/src/generate_data.py

Output:
    ml/data/training_data.csv
"""

import json
import os
import sys

import numpy as np
import pandas as pd


# ── Paths (relative to this script's location) ────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(SCRIPT_DIR)                       # ml/
FEATURE_CONTRACT_PATH = os.path.join(ML_DIR, "feature_names.json")
OUTPUT_DIR = os.path.join(ML_DIR, "data")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "training_data.csv")


# ── Configuration ─────────────────────────────────────────────────────────

RANDOM_SEED = 42
TOTAL_RECORDS = 8000

# 8 scenarios × 40 records = 320 fraud records = 4% of 8000
RECORDS_PER_SCENARIO = 40

# Columns that must NEVER appear as model input features
BANNED_COLUMNS = [
    "is_fraud",
    "fraud_probability",
    "risk_score",
    "shap_values",
    "shap_reasons",
    "approval_decision",
    "routing_decision",
]

# Binary features (for validation)
BINARY_FEATURES = [
    "po_exists",
    "po_approved",
    "grn_exists",
    "vendor_approved",
    "duplicate_invoice",
    "bank_account_changed",
    "new_vendor",
    "unusual_time",
    "suspicious_channel",
    "possible_split_payment",
]

# Fraud scenario names (for reporting — not stored in dataset)
SCENARIO_NAMES = [
    "fake_invoice",
    "changed_bank_account",
    "inflated_invoice",
    "duplicate_invoice",
    "split_payment",
    "unusual_timing",
    "suspicious_channel",
    "new_vendor_large_payment",
]


# ══════════════════════════════════════════════════════════════════════════
# Feature contract
# ══════════════════════════════════════════════════════════════════════════

def load_feature_names():
    """Load the canonical 17-feature list from feature_names.json."""
    if not os.path.exists(FEATURE_CONTRACT_PATH):
        print(f"ERROR: Feature contract not found at {FEATURE_CONTRACT_PATH}")
        sys.exit(1)

    with open(FEATURE_CONTRACT_PATH) as f:
        features = json.load(f)

    print(f"  Loaded {len(features)} features from feature_names.json")

    # Safety check — no banned columns in the contract
    for banned in BANNED_COLUMNS:
        if banned in features:
            print(f"ERROR: Banned column '{banned}' found in feature contract!")
            sys.exit(1)

    return features


# ══════════════════════════════════════════════════════════════════════════
# Genuine record generation
# ══════════════════════════════════════════════════════════════════════════

def generate_genuine_records(n, rng):
    """
    Generate n genuine (non-fraudulent) payment transactions.

    Genuine records have mostly normal/healthy values:
    - POs exist and are approved (~95%)
    - GRNs exist (~92%)
    - Vendors are approved and established
    - Invoice amounts closely match PO amounts
    - Very few flags for duplicates, bank changes, etc.
    - High document quality

    A small percentage of genuine records will have occasional flags
    (e.g. a legitimate bank account change, or overtime work causing
    unusual timing).  This prevents the model from overfitting on any
    single feature.
    """
    records = {}

    # --- Purchase order & goods receipt ---
    records["po_exists"] = rng.choice([0, 1], size=n, p=[0.05, 0.95])
    # PO can only be approved if it exists
    records["po_approved"] = np.where(
        records["po_exists"] == 1,
        rng.choice([0, 1], size=n, p=[0.03, 0.97]),
        0,
    )
    records["grn_exists"] = rng.choice([0, 1], size=n, p=[0.08, 0.92])
    records["vendor_approved"] = rng.choice([0, 1], size=n, p=[0.04, 0.96])

    # --- Invoice-to-PO amount ratio (close to 1.0 for genuine) ---
    records["invoice_po_amount_ratio"] = np.clip(
        rng.normal(loc=1.0, scale=0.05, size=n), 0.85, 1.15
    ).round(4)

    # --- Risk flags (mostly 0, with rare legitimate 1s) ---
    records["duplicate_invoice"] = rng.choice([0, 1], size=n, p=[0.99, 0.01])
    records["bank_account_changed"] = rng.choice([0, 1], size=n, p=[0.97, 0.03])
    records["new_vendor"] = rng.choice([0, 1], size=n, p=[0.90, 0.10])

    # --- Vendor history ---
    # Established vendors: 180–3650 days, 5–200 past payments
    # New-but-legitimate vendors: 30–180 days, 0–5 past payments
    records["vendor_age_days"] = np.where(
        records["new_vendor"] == 1,
        rng.integers(30, 180, size=n),
        rng.integers(180, 3650, size=n),
    )
    records["past_genuine_payments"] = np.where(
        records["new_vendor"] == 1,
        rng.integers(0, 6, size=n),       # 0–5
        rng.integers(5, 201, size=n),     # 5–200
    )

    # --- Amount relative to vendor average (close to 1.0) ---
    records["amount_vs_vendor_avg"] = np.clip(
        rng.normal(loc=1.0, scale=0.3, size=n), 0.2, 3.0
    ).round(4)

    # --- Timing and channel ---
    records["unusual_time"] = rng.choice([0, 1], size=n, p=[0.95, 0.05])
    records["suspicious_channel"] = rng.choice([0, 1], size=n, p=[0.97, 0.03])

    # --- Payment velocity ---
    records["payments_last_24h"] = rng.integers(0, 4, size=n)   # 0–3
    records["amount_last_24h"] = np.clip(
        rng.exponential(scale=15000, size=n), 0, 200000
    ).round(2)

    # --- Split payments & document quality ---
    records["possible_split_payment"] = rng.choice([0, 1], size=n, p=[0.98, 0.02])
    records["document_quality_score"] = np.clip(
        rng.normal(loc=0.85, scale=0.10, size=n), 0.0, 1.0
    ).round(4)

    return records


# ══════════════════════════════════════════════════════════════════════════
# Fraud record generation
# ══════════════════════════════════════════════════════════════════════════

def generate_fraud_base(n, rng):
    """
    Generate base features for fraud records (before scenario overrides).

    Compared to genuine records, the base fraud profile has slightly
    elevated rates for several risk flags.  This means fraudulent
    transactions tend to carry multiple weak signals even beyond their
    primary fraud pattern — the model must learn *combinations*.
    """
    records = {}

    records["po_exists"] = rng.choice([0, 1], size=n, p=[0.20, 0.80])
    records["po_approved"] = np.where(
        records["po_exists"] == 1,
        rng.choice([0, 1], size=n, p=[0.15, 0.85]),
        0,
    )
    records["grn_exists"] = rng.choice([0, 1], size=n, p=[0.25, 0.75])
    records["vendor_approved"] = rng.choice([0, 1], size=n, p=[0.15, 0.85])

    records["invoice_po_amount_ratio"] = np.clip(
        rng.normal(loc=1.10, scale=0.15, size=n), 0.70, 1.80
    ).round(4)

    records["duplicate_invoice"] = rng.choice([0, 1], size=n, p=[0.90, 0.10])
    records["bank_account_changed"] = rng.choice([0, 1], size=n, p=[0.80, 0.20])
    records["new_vendor"] = rng.choice([0, 1], size=n, p=[0.70, 0.30])

    records["vendor_age_days"] = np.where(
        records["new_vendor"] == 1,
        rng.integers(1, 90, size=n),
        rng.integers(90, 2000, size=n),
    )
    records["past_genuine_payments"] = np.where(
        records["new_vendor"] == 1,
        rng.integers(0, 3, size=n),
        rng.integers(2, 50, size=n),
    )

    records["amount_vs_vendor_avg"] = np.clip(
        rng.normal(loc=1.5, scale=0.6, size=n), 0.3, 5.0
    ).round(4)

    records["unusual_time"] = rng.choice([0, 1], size=n, p=[0.70, 0.30])
    records["suspicious_channel"] = rng.choice([0, 1], size=n, p=[0.80, 0.20])

    records["payments_last_24h"] = rng.integers(0, 8, size=n)
    records["amount_last_24h"] = np.clip(
        rng.exponential(scale=30000, size=n), 0, 300000
    ).round(2)

    records["possible_split_payment"] = rng.choice([0, 1], size=n, p=[0.90, 0.10])
    records["document_quality_score"] = np.clip(
        rng.normal(loc=0.60, scale=0.20, size=n), 0.0, 1.0
    ).round(4)

    return records


# ── Scenario-specific overrides ───────────────────────────────────────────

def apply_fake_invoice(records, n, rng):
    """Scenario 1 — Fake invoice / missing PO.
    No purchase order, no goods receipt, poor documentation."""
    records["po_exists"] = np.zeros(n, dtype=int)
    records["po_approved"] = np.zeros(n, dtype=int)
    records["grn_exists"] = rng.choice([0, 1], size=n, p=[0.85, 0.15])
    records["document_quality_score"] = np.clip(
        rng.normal(loc=0.30, scale=0.15, size=n), 0.0, 0.70
    ).round(4)
    records["vendor_approved"] = rng.choice([0, 1], size=n, p=[0.40, 0.60])
    return records


def apply_changed_bank_account(records, n, rng):
    """Scenario 2 — Changed bank account.
    Bank details recently changed, often combined with unusual amounts."""
    records["bank_account_changed"] = np.ones(n, dtype=int)
    records["amount_vs_vendor_avg"] = np.clip(
        rng.normal(loc=2.0, scale=0.8, size=n), 1.0, 5.0
    ).round(4)
    records["unusual_time"] = rng.choice([0, 1], size=n, p=[0.50, 0.50])
    return records


def apply_inflated_invoice(records, n, rng):
    """Scenario 3 — Inflated invoice.
    Invoice amount significantly exceeds PO amount."""
    records["invoice_po_amount_ratio"] = np.clip(
        rng.normal(loc=1.80, scale=0.40, size=n), 1.30, 3.50
    ).round(4)
    # Inflated invoices reference a real PO (that's the inflation vector)
    records["po_exists"] = np.ones(n, dtype=int)
    records["po_approved"] = np.ones(n, dtype=int)
    return records


def apply_duplicate_invoice(records, n, rng):
    """Scenario 4 — Duplicate invoice.
    Same invoice submitted again, often with lower doc quality."""
    records["duplicate_invoice"] = np.ones(n, dtype=int)
    records["document_quality_score"] = np.clip(
        rng.normal(loc=0.50, scale=0.15, size=n), 0.10, 0.80
    ).round(4)
    return records


def apply_split_payment(records, n, rng):
    """Scenario 5 — Split payments.
    Large payment split into many smaller ones in a short window."""
    records["possible_split_payment"] = np.ones(n, dtype=int)
    records["payments_last_24h"] = rng.integers(4, 16, size=n)   # 4–15
    records["amount_last_24h"] = np.clip(
        rng.normal(loc=100000, scale=30000, size=n), 50000, 300000
    ).round(2)
    return records


def apply_unusual_timing(records, n, rng):
    """Scenario 6 — Unusual payment timing.
    Payment submitted outside business hours, often with suspicious channel."""
    records["unusual_time"] = np.ones(n, dtype=int)
    records["suspicious_channel"] = rng.choice([0, 1], size=n, p=[0.40, 0.60])
    records["document_quality_score"] = np.clip(
        rng.normal(loc=0.55, scale=0.20, size=n), 0.0, 1.0
    ).round(4)
    return records


def apply_suspicious_channel(records, n, rng):
    """Scenario 7 — Suspicious communication channel.
    Payment requested via unusual channel, sometimes combined with new vendor."""
    records["suspicious_channel"] = np.ones(n, dtype=int)
    records["unusual_time"] = rng.choice([0, 1], size=n, p=[0.40, 0.60])
    records["new_vendor"] = rng.choice([0, 1], size=n, p=[0.50, 0.50])
    records["vendor_age_days"] = np.where(
        records["new_vendor"] == 1,
        rng.integers(1, 60, size=n),
        records["vendor_age_days"],
    )
    return records


def apply_new_vendor_large_payment(records, n, rng):
    """Scenario 8 — New vendor + large payment.
    Recently registered vendor receiving a disproportionately large payment."""
    records["new_vendor"] = np.ones(n, dtype=int)
    records["vendor_age_days"] = rng.integers(1, 30, size=n)
    records["past_genuine_payments"] = rng.integers(0, 2, size=n)   # 0–1
    records["amount_vs_vendor_avg"] = np.clip(
        rng.normal(loc=4.0, scale=1.5, size=n), 2.0, 10.0
    ).round(4)
    records["vendor_approved"] = rng.choice([0, 1], size=n, p=[0.50, 0.50])
    return records


# Map scenario names → apply functions
SCENARIO_FUNCTIONS = {
    "fake_invoice":              apply_fake_invoice,
    "changed_bank_account":      apply_changed_bank_account,
    "inflated_invoice":          apply_inflated_invoice,
    "duplicate_invoice":         apply_duplicate_invoice,
    "split_payment":             apply_split_payment,
    "unusual_timing":            apply_unusual_timing,
    "suspicious_channel":        apply_suspicious_channel,
    "new_vendor_large_payment":  apply_new_vendor_large_payment,
}


# ══════════════════════════════════════════════════════════════════════════
# Dataset assembly
# ══════════════════════════════════════════════════════════════════════════

def generate_dataset(feature_names):
    """Assemble the complete dataset: genuine + 8 fraud scenarios."""
    rng = np.random.default_rng(RANDOM_SEED)

    total_fraud = len(SCENARIO_NAMES) * RECORDS_PER_SCENARIO   # 320
    total_genuine = TOTAL_RECORDS - total_fraud                 # 7680

    print(f"\n  Generating {TOTAL_RECORDS} records:")
    print(f"    Genuine:    {total_genuine}")
    print(f"    Fraudulent: {total_fraud}  ({total_fraud / TOTAL_RECORDS * 100:.1f}%)")
    print(f"    Scenarios:  {len(SCENARIO_NAMES)} x {RECORDS_PER_SCENARIO} each\n")

    all_frames = []

    # ── Genuine records ──
    print("    Generating genuine records ...")
    genuine = generate_genuine_records(total_genuine, rng)
    genuine_df = pd.DataFrame(genuine)[feature_names]
    genuine_df["is_fraud"] = 0
    all_frames.append(genuine_df)

    # ── Fraud records (one batch per scenario) ──
    for scenario in SCENARIO_NAMES:
        n = RECORDS_PER_SCENARIO
        print(f"    Generating fraud scenario: {scenario}  ({n} records)")

        # Start with the elevated-risk base
        fraud_records = generate_fraud_base(n, rng)
        # Apply scenario-specific overrides
        fraud_records = SCENARIO_FUNCTIONS[scenario](fraud_records, n, rng)

        fraud_df = pd.DataFrame(fraud_records)[feature_names]
        fraud_df["is_fraud"] = 1
        all_frames.append(fraud_df)

    # ── Combine & shuffle ──
    print("\n    Combining and shuffling ...")
    dataset = pd.concat(all_frames, ignore_index=True)
    dataset = dataset.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)

    return dataset


# ══════════════════════════════════════════════════════════════════════════
# Validation
# ══════════════════════════════════════════════════════════════════════════

def validate_dataset(df, feature_names):
    """
    Run all validation checks on the generated dataset.
    Prints a detailed report and exits with code 1 if any check fails.
    """
    print("\n" + "=" * 60)
    print("  DATASET VALIDATION")
    print("=" * 60)

    errors = []

    # 1. Row count
    print(f"\n  1. Row count:          {len(df)}")
    if len(df) != TOTAL_RECORDS:
        errors.append(f"Expected {TOTAL_RECORDS} rows, got {len(df)}")

    # 2. Column count (17 features + is_fraud)
    expected_cols = len(feature_names) + 1
    print(f"  2. Column count:       {len(df.columns)}  (expected {expected_cols})")
    if len(df.columns) != expected_cols:
        errors.append(f"Expected {expected_cols} columns, got {len(df.columns)}")

    # 3. Required feature names
    missing = [f for f in feature_names if f not in df.columns]
    print(f"  3. Missing features:   {missing if missing else 'None'}")
    if missing:
        errors.append(f"Missing features: {missing}")

    # 4. Target column
    has_target = "is_fraud" in df.columns
    print(f"  4. 'is_fraud' present: {has_target}")
    if not has_target:
        errors.append("Target column 'is_fraud' not found")

    # 5. Missing values
    null_total = df.isnull().sum().sum()
    print(f"  5. Missing values:     {null_total}")
    if null_total > 0:
        errors.append(f"Found {null_total} missing values")
        for col in df.columns:
            col_nulls = df[col].isnull().sum()
            if col_nulls > 0:
                print(f"       {col}: {col_nulls}")

    # 6. Duplicate rows
    dup_count = df.duplicated().sum()
    print(f"  6. Duplicate rows:     {dup_count}")

    # 7–9. Fraud / genuine breakdown
    fraud_count = int((df["is_fraud"] == 1).sum())
    genuine_count = int((df["is_fraud"] == 0).sum())
    fraud_pct = fraud_count / len(df) * 100
    print(f"  7. Fraud count:        {fraud_count}")
    print(f"  8. Genuine count:      {genuine_count}")
    print(f"  9. Fraud percentage:   {fraud_pct:.2f}%")
    if fraud_pct < 3.0 or fraud_pct > 5.0:
        errors.append(f"Fraud rate {fraud_pct:.2f}% outside 3–5% target range")

    # 10. Binary features contain only 0 and 1
    print("  10. Binary feature check:")
    for feat in BINARY_FEATURES:
        unique = sorted(df[feat].unique())
        ok = all(v in (0, 1) for v in unique)
        tag = "OK" if ok else "FAIL"
        print(f"       {feat}: {unique}  [{tag}]")
        if not ok:
            errors.append(f"Binary feature '{feat}' has non-binary values: {unique}")

    # 11. Numeric feature ranges
    numeric_features = [f for f in feature_names if f not in BINARY_FEATURES]
    print("  11. Numeric feature ranges:")
    for feat in numeric_features:
        lo, hi, mu = df[feat].min(), df[feat].max(), df[feat].mean()
        print(f"       {feat}: min={lo:.4f}  max={hi:.4f}  mean={mu:.4f}")

    # Sanity bounds
    if df["document_quality_score"].min() < 0 or df["document_quality_score"].max() > 1:
        errors.append("document_quality_score outside [0, 1]")
    if df["vendor_age_days"].min() < 0:
        errors.append("vendor_age_days has negative values")
    if df["past_genuine_payments"].min() < 0:
        errors.append("past_genuine_payments has negative values")
    if df["invoice_po_amount_ratio"].min() < 0:
        errors.append("invoice_po_amount_ratio has negative values")

    # 12. Fraud scenario presence
    print("  12. Fraud scenario examples (among is_fraud=1):")
    fraud_df = df[df["is_fraud"] == 1]
    scenario_checks = {
        "fake_invoice": fraud_df[
            (fraud_df["po_exists"] == 0) & (fraud_df["po_approved"] == 0)
        ],
        "changed_bank_account": fraud_df[
            fraud_df["bank_account_changed"] == 1
        ],
        "inflated_invoice": fraud_df[
            fraud_df["invoice_po_amount_ratio"] > 1.3
        ],
        "duplicate_invoice": fraud_df[
            fraud_df["duplicate_invoice"] == 1
        ],
        "split_payment": fraud_df[
            (fraud_df["possible_split_payment"] == 1)
            & (fraud_df["payments_last_24h"] >= 4)
        ],
        "unusual_timing": fraud_df[
            fraud_df["unusual_time"] == 1
        ],
        "suspicious_channel": fraud_df[
            fraud_df["suspicious_channel"] == 1
        ],
        "new_vendor_large_payment": fraud_df[
            (fraud_df["new_vendor"] == 1)
            & (fraud_df["vendor_age_days"] < 30)
            & (fraud_df["amount_vs_vendor_avg"] > 2.0)
        ],
    }
    for name, subset in scenario_checks.items():
        tag = "OK" if len(subset) > 0 else "FAIL"
        print(f"       {name}: {len(subset)} examples  [{tag}]")
        if len(subset) == 0:
            errors.append(f"No examples for fraud scenario: {name}")

    # ── Summary ──
    print("\n" + "=" * 60)
    if errors:
        print(f"  VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"    ✗ {e}")
        print("=" * 60)
        sys.exit(1)
    else:
        print("  ALL CHECKS PASSED")
        print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  TrustGuard — Synthetic Fraud Dataset Generator")
    print("=" * 60)
    print(f"  Random seed:  {RANDOM_SEED}")
    print(f"  Total target: {TOTAL_RECORDS} records")

    # 1. Load feature contract
    feature_names = load_feature_names()

    # 2. Generate dataset
    dataset = generate_dataset(feature_names)

    # 3. Save to CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    dataset.to_csv(OUTPUT_FILE, index=False)
    file_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\n  Saved to: {OUTPUT_FILE}")
    print(f"  File size: {file_kb:.1f} KB")

    # 4. Validate
    validate_dataset(dataset, feature_names)

    # 5. Summary statistics
    print("\n" + "=" * 60)
    print("  FEATURE SUMMARY STATISTICS")
    print("=" * 60)
    print(dataset.describe().round(4).to_string())
    print()


if __name__ == "__main__":
    main()
