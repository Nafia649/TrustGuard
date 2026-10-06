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
│   │   ├── audit_service.py # Hash-chained tamper-evident audit log
│   │   └── seed_service.py  # Acme Ltd demo scenario seeder
│   ├── config.py        # Settings and environment variables
│   ├── database.py      # SQLAlchemy engine and session setup
│   └── main.py          # FastAPI application entry point
├── tests/               # Pytest test suite
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_payments.py
│   └── test_audit.py
├── .env.example         # Environment template
├── requirements.txt     # Python package dependencies
└── README.md
```

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

## API Endpoints (Phase 2)

### 1. Seed Demo Data
- **`POST /seed`**: Seeds deterministic demo data for **Acme Ltd**, including:
  - Policy Version 1 (default thresholds and required roles)
  - Authorized approvers (Senior Administrator, Finance Head, Senior Executive)
  - 4 vendors (Acme Industrial Supplies, Global Logistics Corp, Apex Cloud Infrastructure, Shadow Shell Enterprises)
  - Purchase Orders & Goods Receipts (GRNs)
  - 4 Demo Payment Scenarios:
    - `REQ-DEMO-001`: Scenario 1 (Low risk / Auto-approve candidate)
    - `REQ-DEMO-002`: Scenario 2 (Medium risk / Single signature required)
    - `REQ-DEMO-003`: Scenario 3 (Tamper demo target)
    - `REQ-DEMO-004`: Scenario 4 (High risk / Hold candidate - unapproved shadow vendor, no PO)

### 2. Payment Requests
- **`POST /payment-requests`**: Creates a payment request. Enforces server-side validation against registered vendors, linked POs, and duplicate invoice detection. Emits a hash-chained audit event.
  ```json
  {
    "vendor_id": "VEND-001",
    "amount": 25000.0,
    "currency": "INR",
    "bank_account": "ACME-BANK-001",
    "invoice_id": "INV-2026-901",
    "po_id": "PO-2026-001",
    "channel": "portal",
    "document_quality_score": 0.98,
    "requester_id": "emp_sarah_01"
  }
  ```
- **`GET /payments`**: Lists payments with optional filters:
  - `?status=PENDING`
  - `?vendor_id=VEND-001`
  - `?limit=50&offset=0`
- **`GET /payments/{id}`**: Retrieves a specific payment request by ID.

### 3. Vendors
- **`GET /vendors`**: Lists all registered vendors.
- **`GET /vendors/{id}`**: Gets vendor details by ID.

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
