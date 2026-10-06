"""
REALKEY Virtual WebAuthn Client Simulator.

Provides a 100% standards-compliant client-side WebAuthn simulator for
automated testing and demo environments. Generates genuine ECDSA P-256
keypairs in memory, packages authentic clientDataJSON and CBOR attestation
objects, and returns identical structures to browser WebAuthn API.

CRITICAL SECURITY RULE:
The private key is held strictly inside this client simulator in memory
and is NEVER sent to or stored by the server.
"""

import hashlib
import json
import secrets
from typing import Any, Dict, Optional

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url


class VirtualWebAuthnClient:
    """
    Simulates a hardware or platform WebAuthn authenticator on the client device.
    Supports both registration (credential creation) and assertion (authentication signing).
    """
    def __init__(self, origin: str = "http://localhost:5173", rp_id: str = "localhost") -> None:
        self.default_origin = origin
        self.default_rp_id = rp_id
        # Private key is kept client-side ONLY
        self._private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self._credential_id: Optional[bytes] = None

    @property
    def has_credential(self) -> bool:
        return self._private_key is not None and self._credential_id is not None

    @property
    def public_key_pem(self) -> Optional[str]:
        if not self._private_key:
            return None
        from cryptography.hazmat.primitives import serialization
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def create_credential(
        self,
        options: Dict[str, Any],
        override_origin: Optional[str] = None,
        override_rp_id: Optional[str] = None,
        override_challenge_b64: Optional[str] = None,
        override_credential_id: Optional[bytes] = None,
        corrupt_client_data: bool = False,
        corrupt_attestation: bool = False,
        sign_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Simulates `navigator.credentials.create({ publicKey: options })`.
        Returns the RegistrationCredential dictionary.
        """
        # 1. Generate client-side private key (NEVER exported to server)
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        pub_numbers = self._private_key.public_key().public_numbers()
        x_bytes = pub_numbers.x.to_bytes(32, "big")
        y_bytes = pub_numbers.y.to_bytes(32, "big")

        # 2. Extract parameters from options
        challenge_b64 = override_challenge_b64 or options.get("challenge")
        rp_info = options.get("rp", {})
        rp_id = override_rp_id or rp_info.get("id", self.default_rp_id)
        origin = override_origin or self.default_origin

        # 3. Build clientDataJSON
        if corrupt_client_data:
            client_data_bytes = b"CORRUPTED_CLIENT_DATA_JSON_NOT_VALID_JSON"
        else:
            client_data = {
                "type": "webauthn.create",
                "challenge": challenge_b64,
                "origin": origin,
                "crossOrigin": False,
            }
            client_data_bytes = json.dumps(client_data).encode("utf-8")

        client_data_b64 = bytes_to_base64url(client_data_bytes)

        # 4. Build Attested Credential Data
        # COSE Key representation for ES256 (-7): 1: kty (2=EC2), 3: alg (-7), -1: crv (1=P-256), -2: x, -3: y
        cose_key = {1: 2, 3: -7, -1: 1, -2: x_bytes, -3: y_bytes}
        cose_key_bytes = cbor2.dumps(cose_key)

        self._credential_id = override_credential_id or secrets.token_bytes(16)
        cred_id_len = len(self._credential_id).to_bytes(2, "big")
        aaguid = b"\x00" * 16

        # 5. Build authData
        rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
        # Flags: User Present (0x01) + Attested Credential Data Present (0x40) = 0x41
        flags = bytes([0x41])
        sign_count_bytes = sign_count.to_bytes(4, "big")

        auth_data = rp_id_hash + flags + sign_count_bytes + aaguid + cred_id_len + self._credential_id + cose_key_bytes

        # 6. Build attestationObject with "none" attestation format
        if corrupt_attestation:
            attestation_bytes = b"CORRUPTED_CBOR_ATTESTATION_BYTES"
        else:
            attestation_dict = {
                "fmt": "none",
                "attStmt": {},
                "authData": auth_data,
            }
            attestation_bytes = cbor2.dumps(attestation_dict)

        attestation_b64 = bytes_to_base64url(attestation_bytes)
        cred_id_b64 = bytes_to_base64url(self._credential_id)

        # 7. Construct standard WebAuthn response object
        return {
            "id": cred_id_b64,
            "rawId": cred_id_b64,
            "response": {
                "clientDataJSON": client_data_b64,
                "attestationObject": attestation_b64,
            },
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
        }

    def sign_assertion(
        self,
        options: Dict[str, Any],
        override_credential_id: Optional[bytes] = None,
        override_origin: Optional[str] = None,
        override_rp_id: Optional[str] = None,
        override_challenge_b64: Optional[str] = None,
        override_signature: Optional[bytes] = None,
        sign_count: int = 1,
        corrupt_client_data: bool = False,
        corrupt_signature: bool = False,
    ) -> Dict[str, Any]:
        """
        Simulates `navigator.credentials.get({ publicKey: options })`.
        Signs the assertion challenge with the client-side private key.
        Returns standard AuthenticationCredential dictionary.
        """
        if not self._private_key:
            raise RuntimeError("Simulator has no private key. Run create_credential() first.")

        cred_id = override_credential_id or self._credential_id
        if not cred_id:
            raise RuntimeError("Simulator has no credential ID.")

        challenge_b64 = override_challenge_b64 or options.get("challenge")
        rp_id = override_rp_id or options.get("rpId", self.default_rp_id)
        origin = override_origin or self.default_origin

        # 1. clientDataJSON
        if corrupt_client_data:
            client_data_bytes = b"CORRUPTED_CLIENT_DATA_JSON_NOT_VALID_JSON"
        else:
            client_data = {
                "type": "webauthn.get",
                "challenge": challenge_b64,
                "origin": origin,
                "crossOrigin": False,
            }
            client_data_bytes = json.dumps(client_data).encode("utf-8")

        client_data_b64 = bytes_to_base64url(client_data_bytes)
        client_data_hash = hashlib.sha256(client_data_bytes).digest()

        # 2. authData: rpIdHash (32) + flags (1) + signCount (4)
        rp_id_hash = hashlib.sha256(rp_id.encode("utf-8")).digest()
        flags = bytes([0x01])  # UP (User Present)
        sign_count_bytes = sign_count.to_bytes(4, "big")
        auth_data = rp_id_hash + flags + sign_count_bytes
        auth_data_b64 = bytes_to_base64url(auth_data)

        # 3. Cryptographic Signature over (authData + SHA256(clientDataJSON))
        if override_signature:
            signature_bytes = override_signature
        elif corrupt_signature:
            # Corrupted DER signature
            signature_bytes = b"CORRUPTED_SIGNATURE_BYTES_NOT_VALID_ASN1_DER"
        else:
            data_to_sign = auth_data + client_data_hash
            signature_bytes = self._private_key.sign(data_to_sign, ec.ECDSA(hashes.SHA256()))

        signature_b64 = bytes_to_base64url(signature_bytes)
        cred_id_b64 = bytes_to_base64url(cred_id)

        return {
            "id": cred_id_b64,
            "rawId": cred_id_b64,
            "response": {
                "clientDataJSON": client_data_b64,
                "authenticatorData": auth_data_b64,
                "signature": signature_b64,
                "userHandle": None,
            },
            "type": "public-key",
            "clientExtensionResults": {},
        }
