"""Acceptance tests for the two-worker FastAPI coordinator."""

from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

from server.inference import DemoAssets, build_demo_assets, prediction_checksum
from server.server import create_app


@pytest.fixture(scope="module")
def assets() -> DemoAssets:
    return build_demo_assets(sample_count=40)


@pytest.fixture
def client(assets: DemoAssets) -> TestClient:
    return TestClient(
        create_app(
            assets=assets,
            lease_seconds=30,
            heartbeat_timeout_seconds=30,
            max_shard_attempts=2,
        )
    )


def register(client: TestClient, worker_id: str) -> dict[str, Any]:
    response = client.post(
        "/workers/register",
        json={
            "worker_id": worker_id,
            "hostname": f"{worker_id}.local",
            "platform": "test-platform",
            "available": True,
            "coordinator_url": "http://testserver",
            "capabilities": {"cpu_count": 4},
        },
    )
    assert response.status_code == 200
    return response.json()


def create_job(client: TestClient, sample_count: int = 20) -> dict[str, Any]:
    response = client.post(
        "/demo/prediction-jobs",
        json={"sample_count": sample_count, "shard_count": 2},
    )
    assert response.status_code == 200
    return response.json()


def make_ready(client: TestClient, sample_count: int = 20) -> dict[str, Any]:
    job = create_job(client, sample_count)
    job_id = job["job_id"]
    sharded = client.post(f"/demo/prediction-jobs/{job_id}/advance")
    assert sharded.json()["status"] == "sharded"
    distributed = client.post(f"/demo/prediction-jobs/{job_id}/advance")
    assert distributed.json()["status"] == "distributed"
    return distributed.json()


def result_for(
    client: TestClient,
    worker_id: str,
    claim: dict[str, Any],
    *,
    reverse: bool = False,
    checksum: str | None = None,
) -> dict[str, Any]:
    model = client.app.state.coordinator.assets.model
    predictions = np.asarray(model.predict(np.asarray(claim["inputs"])), dtype=np.int64)
    indexes = list(claim["original_indexes"])
    values = predictions.tolist()
    if reverse:
        indexes.reverse()
        values.reverse()
    return {
        "job_id": claim["job_id"],
        "shard_id": claim["shard_id"],
        "worker_id": worker_id,
        "original_indexes": indexes,
        "predictions": values,
        "checksum": checksum or prediction_checksum(values),
        "duration_seconds": 0.01,
        "success": True,
        "error": None,
    }


def complete_job(client: TestClient) -> dict[str, Any]:
    register(client, "worker-a")
    register(client, "worker-b")
    job = make_ready(client)
    claim_a = client.post("/workers/worker-a/next-shard").json()
    claim_b = client.post("/workers/worker-b/next-shard").json()
    first = client.post("/workers/worker-a/results", json=result_for(client, "worker-a", claim_a))
    assert first.status_code == 200
    final = client.post("/workers/worker-b/results", json=result_for(client, "worker-b", claim_b))
    assert final.status_code == 200
    return final.json()["job"]


def test_new_job_starts_submitted(client: TestClient) -> None:
    job = create_job(client)
    assert job["status"] == "submitted"
    assert all(shard["status"] == "pending" for shard in job["shards"])
    assert job["created_at"] and job["updated_at"]


def test_job_moves_through_lifecycle_in_order(client: TestClient) -> None:
    job = complete_job(client)
    assert job["status"] == "completed"
    assert [event["status"] for event in job["status_history"]] == [
        "submitted",
        "sharded",
        "distributed",
        "processing",
        "verifying",
        "completed",
    ]


def test_advancing_completed_job_is_idempotent(client: TestClient) -> None:
    job = complete_job(client)
    advanced = client.post(f"/demo/prediction-jobs/{job['job_id']}/advance")
    assert advanced.status_code == 200
    assert advanced.json()["status"] == "completed"
    assert advanced.json()["completed_at"] == job["completed_at"]


def test_unknown_job_ids_return_404(client: TestClient) -> None:
    assert client.get("/demo/prediction-jobs/job-missing").status_code == 404
    assert client.post("/demo/prediction-jobs/job-missing/advance").status_code == 404


def test_history_distinguishes_job_groups(client: TestClient) -> None:
    in_progress = create_job(client)
    completed = complete_job(client)
    register(client, "worker-c")
    failed = make_ready(client)
    claim = client.post("/workers/worker-c/next-shard").json()
    bad = result_for(client, "worker-c", claim, checksum="not-the-checksum")
    assert client.post("/workers/worker-c/results", json=bad).status_code == 400

    history = client.get("/demo/prediction-jobs").json()
    groups = {job["job_id"]: job["state_group"] for job in history}
    assert groups[in_progress["job_id"]] == "in_progress"
    assert groups[completed["job_id"]] == "completed"
    assert groups[failed["job_id"]] == "failed"


def test_worker_registration_and_heartbeat(client: TestClient) -> None:
    worker = register(client, "worker-a")
    heartbeat = client.post("/workers/worker-a/heartbeat")
    assert heartbeat.status_code == 200
    assert heartbeat.json()["worker_id"] == worker["worker_id"]
    assert heartbeat.json()["last_heartbeat"] >= worker["last_heartbeat"]


def test_two_workers_receive_different_shards(client: TestClient) -> None:
    register(client, "worker-a")
    register(client, "worker-b")
    make_ready(client)
    claim_a = client.post("/workers/worker-a/next-shard").json()
    claim_b = client.post("/workers/worker-b/next-shard").json()
    assert claim_a["shard_id"] != claim_b["shard_id"]
    assert set(claim_a["original_indexes"]).isdisjoint(claim_b["original_indexes"])


def test_worker_cannot_claim_twice_while_lease_is_active(client: TestClient) -> None:
    register(client, "worker-a")
    make_ready(client)
    assert client.post("/workers/worker-a/next-shard").status_code == 200
    assert client.post("/workers/worker-a/next-shard").status_code == 204


def test_distributed_predictions_exactly_match_baseline(client: TestClient) -> None:
    job = complete_job(client)
    verification = job["verification"]
    assert verification["exact_match_count"] == job["sample_count"]
    assert verification["mismatch_count"] == 0
    assert verification["distributed_checksum"] == verification["baseline_checksum"]


def test_results_merge_in_original_order(client: TestClient) -> None:
    register(client, "worker-a")
    register(client, "worker-b")
    make_ready(client)
    claim_a = client.post("/workers/worker-a/next-shard").json()
    claim_b = client.post("/workers/worker-b/next-shard").json()
    client.post("/workers/worker-a/results", json=result_for(client, "worker-a", claim_a, reverse=True))
    final = client.post(
        "/workers/worker-b/results",
        json=result_for(client, "worker-b", claim_b, reverse=True),
    )
    assert final.status_code == 200
    assert final.json()["job"]["verification"]["mismatch_count"] == 0


def test_unknown_worker_cannot_submit_result(client: TestClient) -> None:
    register(client, "worker-a")
    make_ready(client)
    claim = client.post("/workers/worker-a/next-shard").json()
    payload = result_for(client, "worker-a", claim)
    payload["worker_id"] = "unknown-worker"
    response = client.post("/workers/unknown-worker/results", json=payload)
    assert response.status_code == 404


def test_malformed_result_is_rejected(client: TestClient) -> None:
    register(client, "worker-a")
    response = client.post(
        "/workers/worker-a/results",
        json={
            "job_id": "job-any",
            "shard_id": "shard-any",
            "worker_id": "worker-a",
            "duration_seconds": 0.1,
            "success": True,
        },
    )
    assert response.status_code == 422


def test_duplicate_result_submission_is_idempotent(client: TestClient) -> None:
    register(client, "worker-a")
    register(client, "worker-b")
    make_ready(client)
    claim = client.post("/workers/worker-a/next-shard").json()
    payload = result_for(client, "worker-a", claim)
    first = client.post("/workers/worker-a/results", json=payload)
    duplicate = client.post("/workers/worker-a/results", json=payload)
    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert not first.json()["duplicate"]
    assert duplicate.json()["duplicate"]


def test_expired_lease_can_be_reassigned(assets: DemoAssets) -> None:
    client = TestClient(create_app(assets=assets, lease_seconds=-1, max_shard_attempts=2))
    register(client, "worker-a")
    register(client, "worker-b")
    make_ready(client)
    first = client.post("/workers/worker-a/next-shard").json()
    reassigned = client.post("/workers/worker-b/next-shard").json()
    assert reassigned["shard_id"] == first["shard_id"]
    assert reassigned["attempt_count"] == 2


def test_checksum_mismatch_fails_verification(client: TestClient) -> None:
    register(client, "worker-a")
    job = make_ready(client)
    claim = client.post("/workers/worker-a/next-shard").json()
    response = client.post(
        "/workers/worker-a/results",
        json=result_for(client, "worker-a", claim, checksum="wrong-checksum"),
    )
    assert response.status_code == 400
    failed = client.get(f"/demo/prediction-jobs/{job['job_id']}").json()
    assert failed["status"] == "failed"
    assert "Checksum mismatch" in " ".join(failed["errors"])


def test_worker_failure_does_not_crash_coordinator(client: TestClient) -> None:
    register(client, "worker-a")
    register(client, "worker-b")
    job = make_ready(client)
    claim = client.post("/workers/worker-a/next-shard").json()
    failed_attempt = {
        "job_id": claim["job_id"],
        "shard_id": claim["shard_id"],
        "worker_id": "worker-a",
        "original_indexes": [],
        "predictions": [],
        "checksum": "",
        "duration_seconds": 0.01,
        "success": False,
        "error": "simulated worker failure",
    }
    response = client.post("/workers/worker-a/results", json=failed_attempt)
    reassigned = client.post("/workers/worker-b/next-shard")
    assert response.status_code == 200
    assert response.json()["job"]["status"] == "processing"
    assert reassigned.status_code == 200
    assert reassigned.json()["shard_id"] == claim["shard_id"]
    assert client.get("/health").status_code == 200
    assert client.get(f"/demo/prediction-jobs/{job['job_id']}").status_code == 200
