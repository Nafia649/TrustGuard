# TrustGuard + REALKEY Backend

The backend orchestration layer for **TrustGuard + REALKEY**: an intelligent payment-authorization control layer positioned between ERP/Accounts systems and payment settlement.

> [!NOTE]
> **Hackathon MVP Notice:** This project is a proof-of-concept. No real money is moved. The bank/settlement layer is simulated by a mock ledger, and vendor/transaction data is simulated for demonstration purposes.

---

## Architecture Overview

1. **TrustGuard Orchestration:** Coordinates three-way matching, feature preparation for ML fraud risk scoring (XGBoost + SHAP), and policy-driven routing.
2. **Policy Engine & Risk Routing:** Enforces configurable, versioned routing policies, safety caps, and separation of duties.
3. **REALKEY Integration:** Enforces cryptographic authorization (WebAuthn / Passkeys) binding exact payment bundles to nonces, policy tiers, and authorized roles.
4. **Fail-Closed Security:** Enforces separation of duties, tamper detection, and hash-chained audit logging server-side.

---

## Directory Structure

```text
backend/
├── app/
│   ├── api/             # FastAPI route controllers
│   │   ├── health.py    # Health check endpoint
│   │   ├── seed.py      # Seed data controller
│   │   ├── payments.py  # Payment request lifecycle
│   │   ├── vendors.py   # Vendor directory controller
│   │   ├── scoring.py   # Three-Way Match & ML Risk Scoring orchestration
│   │   ├── policy.py    # Policy configuration & versioning
│   │   └── ...
│   ├── models/          # SQLAlchemy ORM models
│   │   ├── vendor.py
│   │   ├── purchase_order.py
│   │   ├── goods_receipt.py
│   │   ├── payment_request.py
│   │   ├── approver.py
│   │   ├── signature.py
│   │   ├── policy.py
│   │   ├── audit_log.py
│   │   └── ledger.py
│   ├── schemas/         # Pydantic validation schemas
│   ├── services/        # Business logic services
│   │   ├── three_way_match.py # Deterministic Three-Way Match facts
│   │   ├── feature_builder.py # 17 ML features builder & contract validator
│   │   ├── ml_client.py       # ML Adapter calling predict_risk(features)
│   │   ├── policy_engine.py   # Policy evaluation, safety safeguards & versioning
│   │   ├── audit_service.py   # Hash-chained tamper-evident audit log
│   │   └── seed_service.py    # Acme Ltd demo scenario seeder
│   ├── config.py        # Settings and environment variables
│   ├── database.py      # SQLAlchemy engine and session setup
│   └── main.py          # FastAPI application entry point
├── tests/               # Pytest test suite
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_payments.py
│   ├── test_audit.py
│   ├── test_three_way_match.py
│   ├── test_policy.py
│   └── test_scoring_orchestration.py
├── .env.example         # Environment template
├── requirements.txt     # Python package dependencies
└── README.md
```

---

## Three-Way Match Business Logic

The backend executes deterministic business verification checks on invoice submissions:
1. **PO Exists:** Verifies the purchase order exists in the registry for this vendor.
2. **PO Approved:** Ensures the PO status is `APPROVED`.
3. **GRN Exists:** Checks that a Goods Receipt exists and `received == True`.
4. **Vendor Approved:** Checks that the vendor is on the approved vendor list.
5. **Amount Match:** Compares invoice amount against PO amount within configurable tolerance (default 2%).
6. **Duplicate Invoice:** Detects if an invoice number was previously submitted for this vendor.
7. **Bank Account Consistency:** Compares the payment bank account against the approved vendor record.

> [!IMPORTANT]
> **Three-Way Match Facts ≠ ML Score:** Three-way matching checks produce objective business facts. They do not calculate fraud probability or approve payments.

---

## Policy Engine & Risk Routing

The routing engine dynamically reads policy rules from the database and evaluates approval requirements without hardcoded thresholds:

```
ML Risk Score (0-100) + Safety Rules  →  Policy Engine
                                            ↓
   Score < 30 (under caps & matching) →  AUTO_APPROVE   (0 signatures, AUTHORIZED)
   Score 30–70                        →  ONE_SIGNATURE  (1 signature, PENDING_APPROVAL)
   Score 70–90                        →  TWO_SIGNATURES (2 signatures, PENDING_APPROVAL)
   Score > 90                         →  HOLD           (0 signatures, ON_HOLD)
```

### Auto-Approval Safeguards (Mandatory)
A low ML risk score is **not** automatically sufficient to auto-approve. The backend unconditionally verifies:
1. **Single Amount Cap:** Payment amount must be $\le$ `auto_approve_cap_amount` (default ₹50,000).
2. **Cumulative Vendor Cap:** 30-day cumulative auto-approvals for the vendor must not exceed `monthly_auto_approved_cap_per_vendor` (default ₹200,000).
3. **Unchanged Bank Account:** Beneficiary bank details must match registered vendor details.
4. **Established Vendor:** Vendor must not be new (registered $\ge$ 30 days).
5. **Three-Way Match:** PO, approved status, GRN, and amount match must all be satisfied.

If any safeguard fails, the payment is automatically escalated to `ONE_SIGNATURE` or `TWO_SIGNATURES`.

### Mandatory Unconditional Escalations
- **New Vendor:** Escalated to `ONE_SIGNATURE` (cannot be auto-approved).
- **Bank Detail Change:** Escalated to `TWO_SIGNATURES` for dual cryptographic sign-off.
- **Unapproved Vendor or Duplicate Invoice:** Immediately placed on `HOLD`.

---

## Scoring Orchestration Pipeline (Phase 5)

When `POST /payments/{id}/score` is called, the backend executes the end-to-end orchestration pipeline:

```
Payment Request
      ↓
Three-Way Match (Business facts)
      ↓
Feature Builder (Exact 17 ML features, zero fabrication)
      ↓
ML Client Adapter (predict_risk)
      ↓
Fraud Probability + Risk Score (0-100) + SHAP Reasons
      ↓
Policy Engine (Dynamic thresholds + safety rules)
      ↓
Routing Determination (AUTO_APPROVE / ONE_SIGNATURE / TWO_SIGNATURES / HOLD)
      ↓
Database Persistence (Updates status, score, routing tier, required signatures)
      ↓
Audit Log (Tamper-evident SHA-256 chained entry)
      ↓
Frontend Response
```

### ML Pluggability
The ML adapter (`backend/app/services/ml_client.py`) provides a clean interface for the ML teammate:
- If `ML_PROVIDER=mock`, it uses a deterministic testing mock.
- To connect the trained XGBoost model, the ML teammate implements `predict_risk(features)` under `ml.predict`, and setting `ML_PROVIDER=real` routes all inference to the real model seamlessly without any backend code refactoring.

---

## The 17 Canonical Input Features

| # | Feature | Type | Derivation Source |
|---|---------|------|-------------------|
| 1 | `po_exists` | binary (0/1) | PO lookup in database for vendor |
| 2 | `po_approved` | binary (0/1) | Status of linked Purchase Order |
| 3 | `grn_exists` | binary (0/1) | GoodsReceipt lookup with received=True |
| 4 | `vendor_approved` | binary (0/1) | Vendor approved status |
| 5 | `invoice_po_amount_ratio` | float | `invoice_amount / po_amount` (requires PO) |
| 6 | `duplicate_invoice` | binary (0/1) | Uniqueness check across payment requests |
| 7 | `bank_account_changed` | binary (0/1) | Beneficiary bank vs vendor bank record |
| 8 | `new_vendor` | binary (0/1) | Vendor registered within past 30 days |
| 9 | `vendor_age_days` | int | Days since vendor onboarding date |
| 10 | `past_genuine_payments` | int | Count of historical authorized/released payments |
| 11 | `amount_vs_vendor_avg` | float | `amount / vendor_usual_mean` (requires baseline) |
| 12 | `unusual_time` | binary (0/1) | Submission off-hours (<8am, >=7pm) or weekends |
| 13 | `suspicious_channel` | binary (0/1) | Channel outside standard portal/erp/edi |
| 14 | `payments_last_24h` | int | Payment requests submitted in past 24 hours |
| 15 | `amount_last_24h` | float | Sum of payment amounts submitted in past 24 hours |
| 16 | `possible_split_payment` | binary (0/1) | Multiple transactions to same vendor in 24h |
| 17 | `document_quality_score` | float (0–1) | Supporting document quality score |

---

## Local Setup & Installation

### 1. Prerequisites
- Python 3.10+
- pip

### 2. Virtual Environment Setup
From the repository root or `backend` folder:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configuration
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```

---

## Running the Application

Start the development server with Uvicorn:
```powershell
# From the backend directory
uvicorn app.main:app --reload --port 8000
```

Once running:
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## API Endpoints

### 1. Seed Demo Data
- **`POST /seed`**: Seeds deterministic demo data for **Acme Ltd**.

### 2. Payment Requests
- **`POST /payment-requests`**: Creates a payment request.
- **`GET /payments`**: Lists payments with optional filters.
- **`GET /payments/{id}`**: Retrieves a specific payment request by ID.

### 3. Scoring & Policy Routing
- **`POST /payments/{id}/score`**: Orchestrates Three-Way Match, derives ML features, queries ML model, evaluates Policy Engine routing, persists routing tier & status, and writes to audit log.
  ```json
  {
    "request_id": "REQ-DEMO-001",
    "status": "AUTHORIZED",
    "risk_score": 18,
    "fraud_probability": 0.18,
    "routing_tier": "AUTO_APPROVE",
    "required_signatures": 0,
    "reasons": [],
    "business_checks": { "po_exists": 1, "po_approved": 1, "amount_match": true },
    "routing": { "routing_tier": "AUTO_APPROVE", "status": "AUTHORIZED" }
  }
  ```

### 4. Policy Configuration & Versioning
- **`GET /policy`**: Retrieves the currently active policy configuration.
- **`PUT /policy`**: Updates policy thresholds, creates a new immutable version, and logs an audit record.
- **`GET /policy/history`**: Lists full version history of all policies.

---

## Running Tests

Execute the automated test suite using pytest:
```powershell
pytest
```
Or with verbose output:
```powershell
pytest -v
```
