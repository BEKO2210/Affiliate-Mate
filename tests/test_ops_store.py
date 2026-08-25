from datetime import UTC, datetime

import pytest

from affiliate_mate.ops_store import (
    IdempotencyState,
    JobState,
    OpsConflictError,
    OpsStore,
)


def now(hour: int = 1) -> datetime:
    return datetime(2026, 1, 1, hour, tzinfo=UTC)


def test_job_lifecycle_is_versioned_and_resumable(tmp_path) -> None:
    with OpsStore(tmp_path / "ops.sqlite3") as store:
        job, created = store.begin_job(
            job_key="render:1",
            kind="render",
            payload={"package": "abc"},
            at=now(),
        )
        assert created
        assert job.state is JobState.RUNNING
        assert job.version == 1
        assert store.list_resumable_jobs() == [job]

        checkpointed = store.checkpoint_job(
            job.job_key,
            {"frame": 250},
            expected_version=1,
            at=now(2),
        )
        assert checkpointed.version == 2
        assert checkpointed.checkpoint == {"frame": 250}

        completed = store.complete_job(
            job.job_key,
            {"artifact": "video.mp4"},
            expected_version=2,
            at=now(3),
        )
        assert completed.state is JobState.SUCCEEDED
        assert completed.version == 3
        assert completed.result == {"artifact": "video.mp4"}
        assert store.list_resumable_jobs() == []


def test_identical_job_replay_is_idempotent_but_different_input_conflicts(tmp_path) -> None:
    with OpsStore(tmp_path / "ops.sqlite3") as store:
        first, created = store.begin_job(
            job_key="job-1",
            kind="upload",
            payload={"digest": "a"},
            at=now(),
        )
        replay, replay_created = store.begin_job(
            job_key="job-1",
            kind="upload",
            payload={"digest": "a"},
            at=now(2),
        )
        assert created
        assert not replay_created
        assert replay == first
        with pytest.raises(OpsConflictError, match="different input"):
            store.begin_job(
                job_key="job-1",
                kind="upload",
                payload={"digest": "b"},
                at=now(3),
            )


def test_stale_checkpoint_version_is_rejected(tmp_path) -> None:
    with OpsStore(tmp_path / "ops.sqlite3") as store:
        job, _ = store.begin_job(
            job_key="job-1",
            kind="render",
            payload={},
            at=now(),
        )
        store.checkpoint_job(job.job_key, {"step": 1}, expected_version=1, at=now(2))
        with pytest.raises(OpsConflictError, match="expected version 1"):
            store.checkpoint_job(job.job_key, {"step": 2}, expected_version=1, at=now(3))


def test_external_idempotency_key_cannot_be_rebound(tmp_path) -> None:
    with OpsStore(tmp_path / "ops.sqlite3") as store:
        claim, created = store.claim_idempotency(
            operation="youtube.publish",
            key="package-sha",
            request={"video": "abc"},
            at=now(),
        )
        assert created
        assert claim.state is IdempotencyState.STARTED
        replay, replay_created = store.claim_idempotency(
            operation="youtube.publish",
            key="package-sha",
            request={"video": "abc"},
            at=now(2),
        )
        assert not replay_created
        assert replay == claim

        with pytest.raises(OpsConflictError, match="different request"):
            store.claim_idempotency(
                operation="youtube.publish",
                key="package-sha",
                request={"video": "different"},
                at=now(3),
            )

        completed = store.complete_idempotency(
            operation="youtube.publish",
            key="package-sha",
            response={"video_id": "xyz"},
            at=now(3),
        )
        assert completed.state is IdempotencyState.COMPLETED
        assert completed.response_digest is not None
        same = store.complete_idempotency(
            operation="youtube.publish",
            key="package-sha",
            response={"video_id": "xyz"},
            at=now(4),
        )
        assert same == completed
        with pytest.raises(OpsConflictError, match="another response"):
            store.complete_idempotency(
                operation="youtube.publish",
                key="package-sha",
                response={"video_id": "other"},
                at=now(4),
            )
