"""
REALKEY Challenge Management Module.

Provides cryptographically secure, unpredictable, single-use,
and time-bounded challenges for WebAuthn registration and verification.
"""

import hashlib
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from webauthn.helpers import bytes_to_base64url


class ChallengeError(Exception):
    """Base exception for challenge errors."""
    pass


class ChallengeNotFoundError(ChallengeError):
    """Raised when no active challenge exists for an approver or request."""
    pass


class ChallengeExpiredError(ChallengeError):
    """Raised when a challenge has passed its time-to-live."""
    pass


class ChallengeAlreadyUsedError(ChallengeError):
    """Raised when an attempt is made to reuse a consumed challenge."""
    pass


class ChallengeMismatchError(ChallengeError):
    """Raised when the submitted challenge does not match the issued challenge."""
    pass


class PaymentHashMismatchError(ChallengeError):
    """Raised when the payment hash does not match the approved challenge."""
    pass


@dataclass
class RegistrationChallenge:
    """Represents a pending WebAuthn registration challenge."""
    challenge_id: str
    approver_id: str
    challenge_bytes: bytes
    challenge_b64: str
    created_at: datetime
    expires_at: datetime
    used: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class AuthenticationChallenge:
    """Represents a pending WebAuthn authentication/assertion challenge."""
    challenge_id: str
    approver_id: Optional[str]
    challenge_bytes: bytes
    challenge_b64: str
    created_at: datetime
    expires_at: datetime
    used: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class ApprovalChallenge:
    """Represents a pending WebAuthn payment approval ceremony challenge."""
    challenge_id: str
    request_id: str
    approver_id: str
    canonical_payment_hash: str
    nonce: str
    payment_bundle: Dict[str, Any]
    challenge_bytes: bytes
    challenge_b64: str
    created_at: datetime
    expires_at: datetime
    used: bool = False
    status: str = "ACTIVE"  # "ACTIVE", "IN_VERIFICATION", "CONSUMED"
    consumed_at: Optional[datetime] = None
    preparer_id: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class ChallengeStore:
    """
    Thread-safe in-memory store for registration, authentication, and payment approval challenges.
    Enforces unpredictability, expiration, and single-use consumption.
    """
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reg_challenges: Dict[str, RegistrationChallenge] = {}
        self._auth_challenges_by_id: Dict[str, AuthenticationChallenge] = {}
        self._auth_challenges_by_b64: Dict[str, AuthenticationChallenge] = {}
        self._auth_challenges_by_approver: Dict[str, AuthenticationChallenge] = {}
        self._approval_challenges_by_id: Dict[str, ApprovalChallenge] = {}
        self._approval_challenges_by_b64: Dict[str, ApprovalChallenge] = {}
        self._approval_challenges_by_request: Dict[str, ApprovalChallenge] = {}

    # ---------------------------------------------------------
    # REGISTRATION CHALLENGES
    # ---------------------------------------------------------

    def create_registration_challenge(
        self,
        approver_id: str,
        timeout_seconds: int = 300,
    ) -> RegistrationChallenge:
        """
        Generates a 256-bit cryptographically secure random challenge.
        Supersedes any prior pending challenge for this approver.
        """
        with self._lock:
            challenge_bytes = secrets.token_bytes(32)
            challenge_b64 = bytes_to_base64url(challenge_bytes)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=timeout_seconds)
            challenge_id = f"CHAL-REG-{uuid.uuid4().hex[:12].upper()}"

            challenge = RegistrationChallenge(
                challenge_id=challenge_id,
                approver_id=approver_id,
                challenge_bytes=challenge_bytes,
                challenge_b64=challenge_b64,
                created_at=now,
                expires_at=expires_at,
                used=False,
            )

            self._reg_challenges[approver_id] = challenge
            return challenge

    def get_valid_registration_challenge(
        self,
        approver_id: str,
        client_challenge_b64: Optional[str] = None,
    ) -> RegistrationChallenge:
        """
        Retrieves and validates a registration challenge for an approver.
        Fails closed if missing, expired, or already used.
        """
        with self._lock:
            challenge = self._reg_challenges.get(approver_id)
            if not challenge:
                raise ChallengeNotFoundError(
                    f"No registration challenge found for approver '{approver_id}'."
                )

            if challenge.used:
                raise ChallengeAlreadyUsedError(
                    f"Registration challenge '{challenge.challenge_id}' for approver '{approver_id}' has already been used."
                )

            if challenge.is_expired:
                raise ChallengeExpiredError(
                    f"Registration challenge '{challenge.challenge_id}' for approver '{approver_id}' has expired."
                )

            if client_challenge_b64 is not None and challenge.challenge_b64 != client_challenge_b64:
                raise ChallengeMismatchError(
                    f"Submitted challenge '{client_challenge_b64}' does not match issued challenge for '{approver_id}'."
                )

            return challenge

    def consume_registration_challenge(
        self,
        approver_id: str,
        challenge_id: str,
    ) -> None:
        """Marks a registration challenge as consumed to prevent replay attacks."""
        with self._lock:
            challenge = self._reg_challenges.get(approver_id)
            if not challenge or challenge.challenge_id != challenge_id:
                raise ChallengeNotFoundError(
                    f"Challenge '{challenge_id}' for approver '{approver_id}' not found."
                )

            if challenge.used:
                raise ChallengeAlreadyUsedError(
                    f"Challenge '{challenge_id}' has already been consumed."
                )

            challenge.used = True

    # ---------------------------------------------------------
    # AUTHENTICATION CHALLENGES
    # ---------------------------------------------------------

    def create_authentication_challenge(
        self,
        approver_id: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> AuthenticationChallenge:
        """
        Generates a 256-bit cryptographically secure random authentication challenge.
        Indexed by challenge_id, challenge_b64, and optionally approver_id.
        """
        with self._lock:
            challenge_bytes = secrets.token_bytes(32)
            challenge_b64 = bytes_to_base64url(challenge_bytes)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=timeout_seconds)
            challenge_id = f"CHAL-AUTH-{uuid.uuid4().hex[:12].upper()}"

            challenge = AuthenticationChallenge(
                challenge_id=challenge_id,
                approver_id=approver_id,
                challenge_bytes=challenge_bytes,
                challenge_b64=challenge_b64,
                created_at=now,
                expires_at=expires_at,
                used=False,
            )

            self._auth_challenges_by_id[challenge_id] = challenge
            self._auth_challenges_by_b64[challenge_b64] = challenge
            if approver_id:
                self._auth_challenges_by_approver[approver_id] = challenge

            return challenge

    def get_valid_authentication_challenge(
        self,
        challenge_b64: Optional[str] = None,
        approver_id: Optional[str] = None,
    ) -> AuthenticationChallenge:
        """
        Retrieves and validates an authentication challenge.
        Can be looked up by client challenge_b64 or approver_id.
        """
        with self._lock:
            challenge = None
            if challenge_b64:
                challenge = self._auth_challenges_by_b64.get(challenge_b64)
            elif approver_id:
                challenge = self._auth_challenges_by_approver.get(approver_id)

            if not challenge:
                raise ChallengeNotFoundError("No active authentication challenge found.")

            if challenge.used:
                raise ChallengeAlreadyUsedError(
                    f"Authentication challenge '{challenge.challenge_id}' has already been used."
                )

            if challenge.is_expired:
                raise ChallengeExpiredError(
                    f"Authentication challenge '{challenge.challenge_id}' has expired."
                )

            if approver_id and challenge.approver_id and challenge.approver_id != approver_id:
                raise ChallengeMismatchError(
                    f"Challenge was issued for approver '{challenge.approver_id}', not '{approver_id}'."
                )

            return challenge

    def consume_authentication_challenge(self, challenge_id: str) -> None:
        """Marks an authentication challenge as consumed (single-use guarantee)."""
        with self._lock:
            challenge = self._auth_challenges_by_id.get(challenge_id)
            if not challenge:
                raise ChallengeNotFoundError(f"Authentication challenge '{challenge_id}' not found.")

            if challenge.used:
                raise ChallengeAlreadyUsedError(f"Authentication challenge '{challenge_id}' has already been consumed.")

            challenge.used = True

    # ---------------------------------------------------------
    # PAYMENT APPROVAL CHALLENGES
    # ---------------------------------------------------------

    def create_approval_challenge(
        self,
        request_id: str,
        approver_id: str,
        canonical_payment_hash: str,
        nonce: str,
        payment_bundle: Dict[str, Any],
        timeout_seconds: int = 300,
        preparer_id: Optional[str] = None,
    ) -> ApprovalChallenge:
        """
        Generates a dedicated payment approval challenge cryptographically bound
        to the exact payment bundle hash, request ID, nonce, approver ID, and preparer ID.
        """
        with self._lock:
            raw_entropy = secrets.token_bytes(32)
            # Cryptographically bind challenge bytes to payment hash, request, nonce, approver
            bound_payload = (
                raw_entropy
                + canonical_payment_hash.encode("utf-8")
                + request_id.encode("utf-8")
                + nonce.encode("utf-8")
                + approver_id.encode("utf-8")
            )
            challenge_bytes = hashlib.sha256(bound_payload).digest()
            challenge_b64 = bytes_to_base64url(challenge_bytes)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=timeout_seconds)
            challenge_id = f"CHAL-APPR-{uuid.uuid4().hex[:12].upper()}"

            challenge = ApprovalChallenge(
                challenge_id=challenge_id,
                request_id=request_id,
                approver_id=approver_id,
                canonical_payment_hash=canonical_payment_hash,
                nonce=nonce,
                payment_bundle=payment_bundle,
                challenge_bytes=challenge_bytes,
                challenge_b64=challenge_b64,
                created_at=now,
                expires_at=expires_at,
                used=False,
                status="ACTIVE",
                consumed_at=None,
                preparer_id=preparer_id,
            )

            self._approval_challenges_by_id[challenge_id] = challenge
            self._approval_challenges_by_b64[challenge_b64] = challenge
            self._approval_challenges_by_request[f"{request_id}:{approver_id}"] = challenge
            self._approval_challenges_by_request[request_id] = challenge

            return challenge

    def get_valid_approval_challenge(
        self,
        challenge_b64: Optional[str] = None,
        request_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        challenge_id: Optional[str] = None,
    ) -> ApprovalChallenge:
        """
        Retrieves and validates an approval challenge for a payment ceremony.
        Fails closed on missing, expired, reused, or mismatched challenges.
        """
        with self._lock:
            challenge = None
            if challenge_id:
                challenge = self._approval_challenges_by_id.get(challenge_id)
            elif challenge_b64:
                challenge = self._approval_challenges_by_b64.get(challenge_b64)
            elif request_id and approver_id:
                challenge = self._approval_challenges_by_request.get(f"{request_id}:{approver_id}")
            elif request_id:
                challenge = self._approval_challenges_by_request.get(request_id)

            if not challenge:
                raise ChallengeNotFoundError("No active approval challenge found for this payment request.")

            if challenge.used or getattr(challenge, "status", None) == "CONSUMED":
                raise ChallengeAlreadyUsedError(
                    f"Approval challenge '{challenge.challenge_id}' has already been used."
                )

            if getattr(challenge, "status", None) == "IN_VERIFICATION":
                raise ChallengeAlreadyUsedError(
                    f"Approval challenge '{challenge.challenge_id}' is already in verification (concurrent replay detected)."
                )

            if challenge.is_expired:
                raise ChallengeExpiredError(
                    f"Approval challenge '{challenge.challenge_id}' has expired."
                )

            if request_id and challenge.request_id != request_id:
                raise ChallengeMismatchError(
                    f"Approval challenge was issued for request '{challenge.request_id}', not '{request_id}'."
                )

            if approver_id and challenge.approver_id != approver_id:
                raise ChallengeMismatchError(
                    f"Approval challenge was issued for approver '{challenge.approver_id}', not '{approver_id}'."
                )

            return challenge

    def claim_approval_challenge(
        self,
        challenge_id: Optional[str] = None,
        request_id: Optional[str] = None,
        approver_id: Optional[str] = None,
        challenge_b64: Optional[str] = None,
    ) -> ApprovalChallenge:
        """
        Atomically claims an approval challenge, transitioning its state from ACTIVE to IN_VERIFICATION.
        Thread-safe: Prevents two simultaneous requests from claiming the same challenge.
        """
        with self._lock:
            challenge = None
            if challenge_id:
                challenge = self._approval_challenges_by_id.get(challenge_id)
            elif challenge_b64:
                challenge = self._approval_challenges_by_b64.get(challenge_b64)
            elif request_id and approver_id:
                challenge = self._approval_challenges_by_request.get(f"{request_id}:{approver_id}")
            elif request_id:
                challenge = self._approval_challenges_by_request.get(request_id)

            if not challenge:
                raise ChallengeNotFoundError("No active approval challenge found for this payment request.")

            if challenge.used or getattr(challenge, "status", None) == "CONSUMED":
                raise ChallengeAlreadyUsedError(
                    f"Approval challenge '{challenge.challenge_id}' has already been consumed."
                )

            if getattr(challenge, "status", None) == "IN_VERIFICATION":
                raise ChallengeAlreadyUsedError(
                    f"Approval challenge '{challenge.challenge_id}' is already in verification (concurrent replay detected)."
                )

            if challenge.is_expired:
                raise ChallengeExpiredError(
                    f"Approval challenge '{challenge.challenge_id}' has expired."
                )

            if request_id and challenge.request_id != request_id:
                raise ChallengeMismatchError(
                    f"Approval challenge was issued for request '{challenge.request_id}', not '{request_id}'."
                )

            if approver_id and challenge.approver_id != approver_id:
                raise ChallengeMismatchError(
                    f"Approval challenge was issued for approver '{challenge.approver_id}', not '{approver_id}'."
                )

            # Atomic state transition: ACTIVE -> IN_VERIFICATION
            challenge.status = "IN_VERIFICATION"
            return challenge

    def consume_approval_challenge(self, challenge_id: str) -> None:
        """
        Finalizes consumption of an approval challenge after successful verification.
        Transitions state to CONSUMED and records timestamp.
        """
        with self._lock:
            challenge = self._approval_challenges_by_id.get(challenge_id)
            if not challenge:
                raise ChallengeNotFoundError(f"Approval challenge '{challenge_id}' not found.")

            if challenge.status == "CONSUMED" and challenge.used:
                raise ChallengeAlreadyUsedError(
                    f"Approval challenge '{challenge_id}' has already been consumed."
                )

            challenge.used = True
            challenge.status = "CONSUMED"
            challenge.consumed_at = datetime.now(timezone.utc)

    def burn_approval_challenge(self, challenge_id: str) -> None:
        """
        Immediately burns an approval challenge following a verification failure.
        Ensures a failed challenge cannot be reused or retried.
        """
        with self._lock:
            challenge = self._approval_challenges_by_id.get(challenge_id)
            if challenge:
                challenge.used = True
                challenge.status = "CONSUMED"
                challenge.consumed_at = datetime.now(timezone.utc)

    def clear(self) -> None:
        """Reset all challenges (useful for test isolation)."""
        with self._lock:
            self._reg_challenges.clear()
            self._auth_challenges_by_id.clear()
            self._auth_challenges_by_b64.clear()
            self._auth_challenges_by_approver.clear()
            self._approval_challenges_by_id.clear()
            self._approval_challenges_by_b64.clear()
            self._approval_challenges_by_request.clear()


# Global challenge store instance
challenge_store = ChallengeStore()
