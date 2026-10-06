# REALKEY Integration Contract

## 1. REALKEY Purpose
The REALKEY module provides cryptographic authorization, WebAuthn/Passkey verification, canonical payment bundling, and proof of non-repudiation for TrustGuard payments. It strictly guarantees that an authenticated and authorized approver cryptographically signed the *exact* payment payload without tampering.

## 2. Security Responsibilities
* **REALKEY handles**: 
  * WebAuthn Registration and Authentication (Passkeys).
  * Exact RFC 8785 JSON Canonicalization of 11 payment bundle fields.
  * SHA-256 Payment Hashing.
  * Cryptographic Signature Verification.
  * Replay Protection (Challenge consumption, Nonce-uniqueness, Sign Count Monotonicity).
  * Tamper Detection (comparing signed bundle hash vs active DB state).
  * Separation of Duties (Approver must NOT equal Preparer).
* **Backend teammate handles**: 
  * The generic `PaymentRequest` lifecycle (creating payment records, setting vendor data, ML routing/scores).
  * Updating payment `status` to `AUTHORIZED` immediately after REALKEY returns success.
* **REALKEY does NOT handle**: 
  * Frontend UI state.
  * ML Fraud calculation.
  * Settlement / Ledger.

## 3. Available APIs

### **Payment Approval Ceremony** (Primary Integration Points)
These API routes live in `backend/app/api/payments.py`.

1. **Initiate Approval**: `POST /api/v1/payments/{request_id}/challenge`
   * *Purpose*: Retrieves authoritative payment state, generates a canonical hash, and creates an atomic `ApprovalChallenge`.
   * *Request*: `SigningChallengeRequest { approver_id: str }`
   * *Response*: `SigningChallengeResponse` (Contains `challenge_id`, `nonce`, `canonical_hash`, and WebAuthn `webauthn_options`).

2. **Submit Approval Signature**: `POST /api/v1/payments/{request_id}/approve`
   * *Purpose*: Cryptographically verifies the WebAuthn passkey assertion signature against the exact bundle hash and challenge. Upon success, updates the database and creates an audit `Signature` log.
   * *Request*: `SignatureSubmissionRequest` (Requires `approver_id`, `nonce`, `signature`, `authenticator_data`, `client_data_json`, `challenge_id`).
   * *Response*: `PaymentApprovalResponse`
   * *Note*: If successful, this endpoint will update the payment `status` to `"AUTHORIZED"`.

### **Passkey Registration & Auth**
These API routes live in `backend/app/api/realkey.py`.
* `POST /api/v1/auth/register/challenge`
* `POST /api/v1/auth/register/verify`
* `POST /api/v1/auth/authenticate/challenge`
* `POST /api/v1/auth/authenticate/verify`

## 4. Request/Response Contracts

**`POST /api/v1/payments/{request_id}/challenge`**
```json
// Request
{
  "approver_id": "APP-123"
}
```
```json
// Response
{
  "request_id": "REQ-001",
  "nonce": "1234abcd...",
  "canonical_hash": "e3b0c442...",
  "challenge_id": "CHAL-XYZ",
  "webauthn_options": { /* standard navigator.credentials.get() payload */ }
}
```

**`POST /api/v1/payments/{request_id}/approve`**
```json
// Request
{
  "approver_id": "APP-123",
  "challenge_id": "CHAL-XYZ",
  "nonce": "1234abcd...",
  "signature": "base64_signature_here",
  "authenticator_data": "base64_auth_data_here",
  "client_data_json": "base64_client_data_here"
}
```
```json
// Response
{
  "authorized": true,
  "signature_status": "VERIFIED",
  "payment_status": "AUTHORIZED",
  "message": "Payment successfully and cryptographically approved with REALKEY."
}
```

## 5. Approval Flow

1. The Frontend signals the Backend to start an approval for `REQ-001` (`POST /challenge`).
2. REALKEY reads the *live DB state*, builds an 11-field bundle, computes the `canonical_hash`, generates a `nonce` and a short-lived `challenge_id`.
3. Frontend receives the `webauthn_options` and calls `navigator.credentials.get()`.
4. User validates with their local passkey/biometric.
5. Frontend sends the signed payload back to Backend (`POST /approve`).
6. REALKEY reconstructs the exact payment payload *from the database*, re-hashes it, and cryptographically checks the signature.
7. REALKEY enforces Replay Protection and Separation of Duties.
8. If fully valid, REALKEY returns success and flips the DB record to `AUTHORIZED`.

## 6. Security Guarantees
* **Exact Payment Binding**: The private key signs the `canonical_hash` over 11 critical fields (amount, bank, currency, etc.). Any change breaks the verification.
* **Separation of Duties (SoD)**: Enforced directly via database constraints (Approver ID != Preparer/Requester ID).
* **Single Use (Replay)**: Challenges, nonces, and signatures can strictly only be used once.

## 7. Failure/Error Cases
The module will raise HTTP `400` or `403` standard FastAPI exceptions with the following details:
* `ChallengeExpiredError` / `ChallengeAlreadyUsedError`
* `PaymentBundleValidationError` (Payment was tampered with during signing process)
* `SignatureReplayError` / `NonceAlreadyUsedError`
* `SeparationOfDutiesError` (Cannot approve your own payment)
* `PaymentAlreadyAuthorizedError` (Payment cannot be double-approved)
* `InvalidSignatureError` (WebAuthn validation failed)

## 8. Integration Instructions for the Backend Teammate
* **DO NOT** attempt to recreate the exact payment bundle logic manually. Always rely on `POST /challenge`.
* **DO NOT** process the final authorization update yourself. If `/approve` returns 200, the payment `status` is already set to `AUTHORIZED` by REALKEY safely.
* Feel free to read `request.status` directly from the `PaymentRequest` schema or query it after REALKEY executes.

## 9. What the integrating teammate must NOT bypass
* **Never set `payment.status = "AUTHORIZED"` manually in the business logic.** REALKEY is the sole module permitted to flip this flag, assuring cryptographic backing exists.
* **Never bypass Separation of Duties**.
* **Do not use ML to bypass REALKEY**. ML Fraud scores are advisory; REALKEY signature is mandatory.

## 10. Example REALKEY call flow
See `test_valid_exact_payment_approval` in `backend/tests/test_realkey_approval.py` for a pristine execution of the exact API calling order and payload structures.
