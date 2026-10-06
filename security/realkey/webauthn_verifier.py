"""
REALKEY WebAuthn Verifier Module.

Handles generation of WebAuthn options and server-side cryptographic verification
for both registration ceremonies and authentication/assertion ceremonies.
Ensures zero storage or transmission of private key material.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import cbor2
import webauthn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    decode_credential_public_key,
    decoded_public_key_to_cryptography,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.exceptions import (
    InvalidAuthenticationResponse,
    InvalidRegistrationResponse,
    WebAuthnException,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from security.realkey.challenge import PaymentHashMismatchError


# ---------------------------------------------------------
# EXCEPTIONS
# ---------------------------------------------------------

class WebAuthnSecurityError(Exception):
    """Base exception for all WebAuthn security errors."""
    pass


class WebAuthnRegistrationError(WebAuthnSecurityError):
    """Base exception for WebAuthn registration verification failures."""
    pass


class WebAuthnAuthenticationError(WebAuthnSecurityError):
    """Base exception for WebAuthn assertion verification failures."""
    pass


class InvalidOriginError(WebAuthnSecurityError):
    """Raised when the clientData origin does not match configured origin."""
    pass


class InvalidRPIDError(WebAuthnSecurityError):
    """Raised when the authenticatorData rpIdHash does not match configured RP ID."""
    pass


class InvalidCredentialFormatError(WebAuthnSecurityError):
    """Raised when the incoming credential payload is malformed or invalid."""
    pass


class InvalidSignatureError(WebAuthnAuthenticationError):
    """Raised when the authentication cryptographic assertion signature is invalid."""
    pass


class SignCountReplayError(WebAuthnAuthenticationError):
    """Raised when sign counter is not strictly greater than stored count (replay / clone detected)."""
    pass


class UnknownCredentialError(WebAuthnAuthenticationError):
    """Raised when incoming credential ID is not registered to any active approver."""
    pass


class InactiveApproverError(WebAuthnAuthenticationError):
    """Raised when approver account is deactivated."""
    pass


class ApprovalExpiredError(WebAuthnAuthenticationError):
    """Raised when the payment approval ceremony has expired."""
    pass


# ---------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------

@dataclass
class VerifiedRegistrationResult:
    """Cryptographic artifacts extracted from a verified WebAuthn registration."""
    credential_id: str
    credential_id_bytes: bytes
    public_key_pem: str
    public_key_cose: bytes
    sign_count: int
    aaguid: str


@dataclass
class VerifiedAuthenticationResult:
    """Artifacts extracted from a verified WebAuthn authentication assertion."""
    credential_id: str
    credential_id_bytes: bytes
    new_sign_count: int
    user_verified: bool


@dataclass
class VerifiedPaymentApprovalResult:
    """Cryptographic proof of an exact payment approval ceremony."""
    authorized: bool
    request_id: str
    approver_id: str
    credential_id: str
    canonical_payment_hash: str
    new_sign_count: int
    signature_status: str = "VERIFIED"
    user_verified: bool = False


# ---------------------------------------------------------
# HELPER: PEM TO COSE CONVERSION
# ---------------------------------------------------------

def pem_to_cose(public_key_pem: str) -> bytes:
    """
    Converts a standard PEM SubjectPublicKeyInfo string into CBOR-encoded COSE public key bytes.
    Supports ES256 (P-256) and RS256 (RSA).
    """
    try:
        pub_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception as err:
        raise ValueError(f"Failed to load PEM public key: {err}") from err

    if isinstance(pub_key, ec.EllipticCurvePublicKey):
        numbers = pub_key.public_numbers()
        x_bytes = numbers.x.to_bytes(32, "big")
        y_bytes = numbers.y.to_bytes(32, "big")
        # COSE key map: 1: kty (2=EC2), 3: alg (-7=ES256), -1: crv (1=P-256), -2: x, -3: y
        cose_map = {1: 2, 3: -7, -1: 1, -2: x_bytes, -3: y_bytes}
        return cbor2.dumps(cose_map)

    if isinstance(pub_key, rsa.RSAPublicKey):
        numbers = pub_key.public_numbers()
        n_bytes = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
        e_bytes = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
        # COSE key map: 1: kty (3=RSA), 3: alg (-257=RS256), -1: n, -2: e
        cose_map = {1: 3, 3: -257, -1: n_bytes, -2: e_bytes}
        return cbor2.dumps(cose_map)

    raise ValueError(f"Unsupported public key type: {type(pub_key).__name__}")


# ---------------------------------------------------------
# REGISTRATION IMPLEMENTATION
# ---------------------------------------------------------

def generate_registration_options(
    approver_id: str,
    approver_name: str,
    rp_id: str,
    rp_name: str,
    challenge_bytes: bytes,
    timeout_ms: int = 60000,
) -> Dict[str, Any]:
    """
    Generates standard W3C WebAuthn PublicKeyCredentialCreationOptions.
    JSON-serializable dictionary ready for navigator.credentials.create().
    """
    options = webauthn.generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_name=approver_id,
        user_id=approver_id.encode("utf-8"),
        user_display_name=approver_name,
        challenge=challenge_bytes,
        timeout=timeout_ms,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
            COSEAlgorithmIdentifier.EDDSA,
        ],
    )

    options_json_str = webauthn.options_to_json(options)
    return json.loads(options_json_str)


def verify_registration(
    credential_payload: Union[str, Dict[str, Any]],
    expected_challenge: bytes,
    expected_rp_id: str,
    expected_origin: Union[str, List[str]],
    require_user_presence: bool = True,
    require_user_verification: bool = False,
) -> VerifiedRegistrationResult:
    """Cryptographically verifies a WebAuthn registration response server-side."""
    try:
        verified = webauthn.verify_registration_response(
            credential=credential_payload,
            expected_challenge=expected_challenge,
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
            require_user_presence=require_user_presence,
            require_user_verification=require_user_verification,
            supported_pub_key_algs=[
                COSEAlgorithmIdentifier.ECDSA_SHA_256,
                COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
                COSEAlgorithmIdentifier.EDDSA,
            ],
        )
    except InvalidRegistrationResponse as err:
        err_msg = str(err)
        err_lower = err_msg.lower()
        if "origin" in err_lower:
            raise InvalidOriginError(f"WebAuthn origin verification failed: {err}") from err
        if "rp id" in err_lower:
            raise InvalidRPIDError(f"WebAuthn RP ID verification failed: {err}") from err
        if "challenge" in err_lower or "structure" in err_lower or "format" in err_lower:
            raise InvalidCredentialFormatError(f"WebAuthn credential format invalid: {err}") from err
        raise WebAuthnRegistrationError(f"WebAuthn registration verification rejected: {err}") from err
    except WebAuthnException as err:
        raise InvalidCredentialFormatError(f"WebAuthn credential payload rejected: {err}") from err
    except Exception as err:
        raise WebAuthnRegistrationError(f"Unexpected error during WebAuthn verification: {err}") from err

    cred_id_str = bytes_to_base64url(verified.credential_id)
    decoded_cose = decode_credential_public_key(verified.credential_public_key)
    crypto_pubkey = decoded_public_key_to_cryptography(decoded_cose)

    # Export exclusively Public Key in standard PEM format (ZERO private key material)
    public_key_pem = crypto_pubkey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return VerifiedRegistrationResult(
        credential_id=cred_id_str,
        credential_id_bytes=verified.credential_id,
        public_key_pem=public_key_pem,
        public_key_cose=verified.credential_public_key,
        sign_count=verified.sign_count,
        aaguid=verified.aaguid,
    )


# ---------------------------------------------------------
# AUTHENTICATION / ASSERTION IMPLEMENTATION
# ---------------------------------------------------------

def generate_authentication_options(
    rp_id: str,
    challenge_bytes: bytes,
    allowed_credential_ids: Optional[Union[List[bytes], List[str]]] = None,
    allow_credentials: Optional[Union[List[bytes], List[str]]] = None,
    timeout_ms: int = 60000,
) -> Dict[str, Any]:
    """
    Generates standard W3C WebAuthn PublicKeyCredentialRequestOptions.
    JSON-serializable dictionary ready for navigator.credentials.get().
    """
    creds = allowed_credential_ids or allow_credentials
    descriptors = None
    if creds:
        descriptors = []
        for cid in creds:
            cid_bytes = base64url_to_bytes(cid) if isinstance(cid, str) else cid
            descriptors.append(
                PublicKeyCredentialDescriptor(
                    id=cid_bytes,
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                )
            )

    options = webauthn.generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge_bytes,
        timeout=timeout_ms,
        allow_credentials=descriptors,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    options_json_str = webauthn.options_to_json(options)
    return json.loads(options_json_str)


def verify_authentication(
    credential_payload: Union[str, Dict[str, Any]],
    expected_challenge: bytes,
    expected_rp_id: str,
    expected_origin: Union[str, List[str]],
    public_key_pem: str,
    current_sign_count: int,
    require_user_presence: bool = True,
    require_user_verification: bool = False,
) -> VerifiedAuthenticationResult:
    """
    Cryptographically verifies a WebAuthn authentication assertion response.

    Verifies:
    1. Origin matches configured origin.
    2. RP ID hash matches SHA-256 of expected RP ID.
    3. Challenge matches the issued unpredictable nonce.
    4. AuthenticatorData UP flag is set (User Presence).
    5. Signature is mathematically valid for public_key_pem.
    6. Sign counter monotonicity check: new_sign_count > current_sign_count (cloning/replay defense).
    """
    cose_public_key = pem_to_cose(public_key_pem)

    try:
        verified = webauthn.verify_authentication_response(
            credential=credential_payload,
            expected_challenge=expected_challenge,
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
            credential_public_key=cose_public_key,
            credential_current_sign_count=current_sign_count,
            require_user_verification=require_user_verification,
        )
    except InvalidAuthenticationResponse as err:
        err_msg = str(err)
        err_lower = err_msg.lower()
        if "origin" in err_lower:
            raise InvalidOriginError(f"Origin verification failed: {err}") from err
        if "rp id" in err_lower:
            raise InvalidRPIDError(f"RP ID verification failed: {err}") from err
        if "signature" in err_lower:
            raise InvalidSignatureError(f"Cryptographic signature verification failed: {err}") from err
        if "sign count" in err_lower or "count" in err_lower:
            raise SignCountReplayError(f"Sign count verification failed (replay or clone): {err}") from err
        if "challenge" in err_lower:
            raise InvalidCredentialFormatError(f"Challenge mismatch or invalid format: {err}") from err
        raise WebAuthnAuthenticationError(f"WebAuthn authentication rejected: {err}") from err
    except WebAuthnException as err:
        raise InvalidCredentialFormatError(f"WebAuthn assertion format invalid: {err}") from err
    except Exception as err:
        raise WebAuthnAuthenticationError(f"Unexpected error during assertion verification: {err}") from err

    cred_id_str = bytes_to_base64url(verified.credential_id)

    return VerifiedAuthenticationResult(
        credential_id=cred_id_str,
        credential_id_bytes=verified.credential_id,
        new_sign_count=verified.new_sign_count,
        user_verified=verified.user_verified,
    )


# ---------------------------------------------------------
# PAYMENT APPROVAL CEREMONY VERIFICATION
# ---------------------------------------------------------

def verify_payment_approval(
    credential_payload: Dict[str, Any],
    expected_challenge: bytes,
    expected_rp_id: str,
    expected_origin: Union[str, List[str]],
    public_key_pem: str,
    current_sign_count: int,
    authoritative_payment_hash: str,
    challenge_payment_hash: str,
    request_id: str,
    approver_id: str,
    require_user_presence: bool = True,
    require_user_verification: bool = False,
) -> VerifiedPaymentApprovalResult:
    """
    Cryptographically verifies that an authorized approver approved the EXACT payment bundle.
    
    1. Verifies that the challenge was issued for this exact canonical payment hash.
    2. Performs full WebAuthn assertion verification (ECDSA P-256 signature, RP ID,
       Origin, UP flag, sign counter increment).
    
    Returns VerifiedPaymentApprovalResult.
    """
    # 1. Cryptographic payment hash binding check
    if authoritative_payment_hash != challenge_payment_hash:
        raise PaymentHashMismatchError(
            f"Payment hash mismatch! Authoritative: '{authoritative_payment_hash}' vs Challenge: '{challenge_payment_hash}'."
        )

    # 2. WebAuthn cryptographic assertion verification
    auth_result = verify_authentication(
        credential_payload=credential_payload,
        expected_challenge=expected_challenge,
        expected_rp_id=expected_rp_id,
        expected_origin=expected_origin,
        public_key_pem=public_key_pem,
        current_sign_count=current_sign_count,
        require_user_presence=require_user_presence,
        require_user_verification=require_user_verification,
    )

    return VerifiedPaymentApprovalResult(
        authorized=True,
        request_id=request_id,
        approver_id=approver_id,
        credential_id=auth_result.credential_id,
        canonical_payment_hash=authoritative_payment_hash,
        new_sign_count=auth_result.new_sign_count,
        signature_status="VERIFIED",
        user_verified=auth_result.user_verified,
    )
