from pathlib import Path

import pytest

from media_api.models import JobRequest
from media_api.store import JobStore


def test_store_job_lifecycle(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    request = {"operation": "youtube.transcript", "url": "https://youtu.be/example"}
    row, created = store.submit("token", request, "same-request")
    assert created and row["status"] == "queued"

    duplicate, created = store.submit("token", request, "same-request")
    assert not created and duplicate["job_id"] == row["job_id"]
    assert store.claim()["job_id"] == row["job_id"]

    store.update(row["job_id"], status="succeeded", stage="complete", progress=1)
    assert store.get(row["job_id"])["status"] == "succeeded"
    assert [event["kind"] for event in store.events(row["job_id"])] == ["queued", "running", "succeeded"]


def test_idempotency_conflict(tmp_path: Path):
    store = JobStore(tmp_path / "jobs.sqlite3")
    store.submit("token", {"operation": "youtube.transcript", "url": "https://youtu.be/a"}, "key")
    with pytest.raises(ValueError, match="idempotency_key_conflict"):
        store.submit("token", {"operation": "youtube.transcript", "url": "https://youtu.be/b"}, "key")


def test_clip_validation():
    request = JobRequest(operation="youtube.clip", url="https://youtu.be/example", start_seconds=5, end_seconds=10)
    assert request.end_seconds - request.start_seconds == 5

    with pytest.raises(ValueError):
        JobRequest(operation="youtube.clip", url="https://youtu.be/example", start_seconds=10, end_seconds=5)
