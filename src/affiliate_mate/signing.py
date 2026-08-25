"""Ed25519 signing for content-addressed release and production manifests."""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ops_backup import sha256_file

SIGNATURE_SCHEMA_VERSION = "affiliate-mate.signature.v1"


def _crypto() -> dict[str, Any]:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Ed25519 support requires the optional security dependencies: "
            "pip install 'affiliate-mate[security]'"
        ) from exc
    return {
        "InvalidSignature": InvalidSignature,
        "serialization": serialization,
        "Ed25519PrivateKey": Ed25519PrivateKey,
        "Ed25519PublicKey": Ed25519PublicKey,
    }


def _validate_digest(value: str, field_name: str = "sha256") -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class SignatureEnvelope:
    sha256: str
    signature_base64: str
    public_key_fingerprint: str
    algorithm: str = "Ed25519"
    schema_version: str = SIGNATURE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SIGNATURE_SCHEMA_VERSION:
            raise ValueError(f"unsupported signature schema: {self.schema_version}")
        if self.algorithm != "Ed25519":
            raise ValueError("unsupported signature algorithm")
        _validate_digest(self.sha256)
        _validate_digest(self.public_key_fingerprint, "public_key_fingerprint")
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("signature_base64 is not valid base64") from exc
        if len(signature) != 64:
            raise ValueError("Ed25519 signature must be 64 bytes")

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "sha256": self.sha256,
            "signature_base64": self.signature_base64,
            "public_key_fingerprint": self.public_key_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "SignatureEnvelope":
        expected = {
            "schema_version",
            "algorithm",
            "sha256",
            "signature_base64",
            "public_key_fingerprint",
        }
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown or missing:
            raise ValueError(
                f"signature envelope keys mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}"
            )
        return cls(**{key: str(payload[key]) for key in expected})


def _public_fingerprint(public_key: object) -> str:
    crypto = _crypto()
    serialization = crypto["serialization"]
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw).hexdigest()


def generate_ed25519_keypair(
    private_key_path: str | Path,
    public_key_path: str | Path,
    *,
    overwrite: bool = False,
) -> str:
    """Generate an Ed25519 key pair. Private key files are created with mode 0600."""

    crypto = _crypto()
    serialization = crypto["serialization"]
    private_type = crypto["Ed25519PrivateKey"]
    private_path = Path(private_key_path).expanduser()
    public_path = Path(public_key_path).expanduser()
    if private_path.resolve() == public_path.resolve():
        raise ValueError("private and public key paths must differ")
    for path in (private_path, public_path):
        if path.exists() and not overwrite:
            raise FileExistsError(f"key destination already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    private_key = private_type.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    private_fd = os.open(private_path, private_flags, 0o600)
    try:
        os.write(private_fd, private_bytes)
        os.fsync(private_fd)
    finally:
        os.close(private_fd)
    public_path.write_bytes(public_bytes)
    return _public_fingerprint(public_key)


def sign_file(path: str | Path, private_key_path: str | Path) -> SignatureEnvelope:
    crypto = _crypto()
    serialization = crypto["serialization"]
    private_type = crypto["Ed25519PrivateKey"]
    artifact_path = Path(path).expanduser()
    private_path = Path(private_key_path).expanduser()
    digest = sha256_file(artifact_path)
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    if not isinstance(private_key, private_type):
        raise TypeError("private key is not Ed25519")
    signature = private_key.sign(bytes.fromhex(digest))
    return SignatureEnvelope(
        sha256=digest,
        signature_base64=base64.b64encode(signature).decode("ascii"),
        public_key_fingerprint=_public_fingerprint(private_key.public_key()),
    )


def verify_file(
    path: str | Path,
    public_key_path: str | Path,
    envelope: SignatureEnvelope,
) -> bool:
    crypto = _crypto()
    invalid_signature = crypto["InvalidSignature"]
    serialization = crypto["serialization"]
    public_type = crypto["Ed25519PublicKey"]
    artifact_path = Path(path).expanduser()
    public_path = Path(public_key_path).expanduser()
    digest = sha256_file(artifact_path)
    if digest != envelope.sha256:
        return False
    public_key = serialization.load_pem_public_key(public_path.read_bytes())
    if not isinstance(public_key, public_type):
        raise TypeError("public key is not Ed25519")
    if _public_fingerprint(public_key) != envelope.public_key_fingerprint:
        return False
    try:
        public_key.verify(
            base64.b64decode(envelope.signature_base64, validate=True),
            bytes.fromhex(digest),
        )
    except invalid_signature:
        return False
    return True
