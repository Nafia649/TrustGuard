# TrustGuard + REALKEY Backend

The backend orchestration layer for **TrustGuard + REALKEY**: an intelligent payment-authorization control layer positioned between ERP/Accounts systems and payment settlement.

> [!NOTE]
> **Hackathon MVP Notice:** This project is a proof-of-concept. No real money is moved. The bank/settlement layer is simulated by a mock ledger, and vendor/transaction data is simulated for demonstration purposes.

---

## Architecture Overview

1. **TrustGuard Orchestration:** Coordinates three-way matching, feature preparation for ML fraud risk scoring (XGBoost + SHAP), and policy-driven routing.
2. **REALKEY Integration:** Enforces cryptographic authorization (WebAuthn / Passkeys) binding exact payment bundles to nonces, policy tiers, and authorized roles.
3. **Fail-Closed Security:** Enforces separation of duties, tamper detection, and hash-chained audit logging server-side.

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
│   └── test_three_way_match.py
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

## ML Integration & 17-Feature Contract

The ML component (`predict_risk(features)`) is owned by the ML teammate. The backend integrates via `services/ml_client.py` and `services/feature_builder.py`.

### The 17 Canonical Input Features

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

### Critical Data Integrity Rule
- **Zero Fabrication:** The backend **never** guesses, defaults, or fabricates an ML feature.
- If a required feature cannot legitimately be derived (e.g. `invoice_po_amount_ratio` when no PO exists, or `amount_vs_vendor_avg` when a vendor has zero history and zero baseline), `feature_builder` raises `MissingFeatureDerivationError`.
- Missing required derivations return HTTP 422 Unprocessable Content.
- Unexpected features are strictly rejected.

### ML Advisory vs. Backend Policy Authority
- **ML Output is Advisory Intelligence Only:** Returns `fraud_probability`, `risk_score` (0–100), and `reasons`.
- **Policy Engine Authority:** The backend never approves a transaction simply because ML returned a low risk score. Mandatory policy rules and separation of duties govern all authorization.

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

Key environment settings:
- `DATABASE_URL`: `sqlite:///./trustguard.db` (Default SQLite for MVP)
- `ML_PROVIDER`: `mock` (Deterministic ML adapter for early integration)
- `WEBAUTHN_RP_ID`: `localhost`
- `ALLOWED_ORIGINS`: Allowed CORS origins for the frontend (e.g. `http://localhost:5173`)

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
- **`POST /seed`**: Seeds deterministic demo data for **Acme Ltd**, including:
  - Policy Version 1 (default thresholds and required roles)
  - Authorized approvers (Senior Administrator, Finance Head, Senior Executive)
  - 4 vendors (Acme Industrial Supplies, Global Logistics Corp, Apex Cloud Infrastructure, Shadow Shell Enterprises)
  - Purchase Orders & Goods Receipts (GRNs)
  - 4 Demo Payment Scenarios (`REQ-DEMO-001` through `REQ-DEMO-004`)

### 2. Payment Requests
- **`POST /payment-requests`**: Creates a payment request. Enforces server-side validation against registered vendors, linked POs, and duplicate invoice detection.
- **`GET /payments`**: Lists payments with optional filters (`status`, `vendor_id`, pagination).
- **`GET /payments/{id}`**: Retrieves a specific payment request by ID.

### 3. Scoring Orchestration (Phase 3)
- **`POST /payments/{id}/score`**: Executes the Three-Way Match, derives the 17 legitimate ML features, invokes `predict_risk(features)`, updates the payment's risk score and reasons, and writes to the audit log.
  - Response clearly separates `business_checks` (facts) from `ml_assessment` (intelligence).
  - Status transitions to `SCORED` (not authorized/approved).

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
