from datetime import UTC, datetime

import pytest

from affiliate_mate.release_manifest import build_release_manifest, verify_release_manifest


def test_release_manifest_verifies_exact_bytes(tmp_path) -> None:
    wheel = tmp_path / "affiliate_mate-1.0.0-py3-none-any.whl"
    sdist = tmp_path / "affiliate_mate-1.0.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")

    manifest = build_release_manifest(
        [wheel, sdist],
        root=tmp_path,
        version="1.0.0",
        commit_sha="a" * 40,
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
    )
    report = verify_release_manifest(manifest, root=tmp_path)

    assert report["passed"] is True
    assert [item["path"] for item in manifest["artifacts"]] == sorted(
        item["path"] for item in manifest["artifacts"]
    )


def test_release_manifest_detects_tampering(tmp_path) -> None:
    artifact = tmp_path / "package.whl"
    artifact.write_bytes(b"original")
    manifest = build_release_manifest(
        [artifact],
        root=tmp_path,
        version="1.0.0",
        commit_sha="b" * 40,
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
    )
    artifact.write_bytes(b"tampered")

    report = verify_release_manifest(manifest, root=tmp_path)
    assert report["passed"] is False
    assert report["checks"][0]["sha256_matches"] is False


def test_release_manifest_rejects_escape_and_bad_commit(tmp_path) -> None:
    outside = tmp_path.parent / "outside.whl"
    outside.write_bytes(b"outside")
    with pytest.raises(ValueError, match="escapes root"):
        build_release_manifest(
            [outside],
            root=tmp_path,
            version="1.0.0",
            commit_sha="c" * 40,
            created_at=datetime(2026, 8, 25, tzinfo=UTC),
        )

    inside = tmp_path / "inside.whl"
    inside.write_bytes(b"inside")
    with pytest.raises(ValueError, match="commit_sha"):
        build_release_manifest(
            [inside],
            root=tmp_path,
            version="1.0.0",
            commit_sha="not-a-sha",
            created_at=datetime(2026, 8, 25, tzinfo=UTC),
        )
