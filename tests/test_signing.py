import os

import pytest

from affiliate_mate.signing import (
    SignatureEnvelope,
    generate_ed25519_keypair,
    sign_file,
    verify_file,
)


def test_sign_and_verify_content_addressed_artifact(tmp_path) -> None:
    artifact = tmp_path / "manifest.json"
    private_key = tmp_path / "keys" / "release-private.pem"
    public_key = tmp_path / "keys" / "release-public.pem"
    artifact.write_text('{"artifact":"abc"}\n', encoding="utf-8")

    fingerprint = generate_ed25519_keypair(private_key, public_key)
    envelope = sign_file(artifact, private_key)

    assert envelope.public_key_fingerprint == fingerprint
    assert verify_file(artifact, public_key, envelope)
    assert os.stat(private_key).st_mode & 0o777 == 0o600


def test_tampered_artifact_fails_signature_verification(tmp_path) -> None:
    artifact = tmp_path / "artifact.bin"
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    artifact.write_bytes(b"original")
    generate_ed25519_keypair(private_key, public_key)
    envelope = sign_file(artifact, private_key)
    artifact.write_bytes(b"tampered")
    assert not verify_file(artifact, public_key, envelope)


def test_signature_envelope_round_trip_is_strict(tmp_path) -> None:
    artifact = tmp_path / "artifact.bin"
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    artifact.write_bytes(b"data")
    generate_ed25519_keypair(private_key, public_key)
    envelope = sign_file(artifact, private_key)
    reconstructed = SignatureEnvelope.from_dict(envelope.to_dict())
    assert reconstructed == envelope

    payload = envelope.to_dict() | {"unexpected": "field"}
    with pytest.raises(ValueError, match="keys mismatch"):
        SignatureEnvelope.from_dict(payload)


def test_key_generation_refuses_overwrite_by_default(tmp_path) -> None:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    generate_ed25519_keypair(private_key, public_key)
    with pytest.raises(FileExistsError):
        generate_ed25519_keypair(private_key, public_key)
