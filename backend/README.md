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
│   ├── config.py        # Settings and environment variables
│   ├── database.py      # SQLAlchemy engine and session setup
│   └── main.py          # FastAPI application entry point
├── tests/               # Pytest test suite
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

## Running Tests

Execute the automated test suite using pytest:
```powershell
pytest
```
Or with verbose output:
```powershell
pytest -v
```
