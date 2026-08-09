"""Acceptance tests for replicated clinical comparison coordination."""

import unittest

from clinical.distributed_compute import (
    ClinicalComputeCoordinator,
    WorkerApprovalError,
    canonical_checksum,
)
from clinical.schemas import (
    ClinicalPredictionJobRequest,
    ComparisonTaskResultRequest,
    ComputeWorkerRegistrationRequest,
)


class TestClinicalComputeCoordinator(unittest.TestCase):
    def setUp(self) -> None:
        self.coordinator = ClinicalComputeCoordinator(
            artifact_checksum="artifact-checksum",
            approved_worker_ids={"worker-a", "worker-b"},
        )
        self.register("worker-a")
        self.register("worker-b")

    def register(self, worker_id: str, hostname: str | None = None) -> None:
        self.coordinator.register_worker(
            ComputeWorkerRegistrationRequest(
                worker_id=worker_id,
                hostname=hostname or f"{worker_id}.local",
                platform="test-platform",
                capabilities={
                    "workload_versions": ["trial2vec-comparison-v1"],
                    "artifact_checksum": "artifact-checksum",
                    "cpu_count": 4,
                    "memory_gb": 8,
                },
            )
        )

    @staticmethod
    def request() -> ClinicalPredictionJobRequest:
        return ClinicalPredictionJobRequest.model_validate(
            {
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "anchor_nct_id": "NCT001",
                        "draft": {"protocol_text": "Protocol A"},
                    }
                ]
            }
        )

    @staticmethod
    def result(candidate_id: str = "candidate-a", similarity: float = 91.2) -> dict:
        return {
            "candidate_id": candidate_id,
            "anchor_nct_id": "NCT001",
            "analysis_type": "trial_similarity_comparison",
            "top_match_similarity": similarity,
        }

    def submit_claim_result(self, worker_id: str, claim: dict, result: dict) -> dict:
        _, job = self.coordinator.submit_result(
            worker_id,
            ComparisonTaskResultRequest(
                job_id=claim["job_id"],
                task_id=claim["task_id"],
                worker_id=worker_id,
                result=result,
                checksum=canonical_checksum(result),
                duration_seconds=0.01,
                success=True,
            ),
        )
        return job

    def test_two_approved_workers_verify_and_aggregate_one_result(self) -> None:
        job = self.coordinator.submit_job(self.request())
        self.assertEqual(job["status"], "queued")
        self.assertEqual(len(job["tasks"]), 2)

        claim_a = self.coordinator.claim_next_task("worker-a")
        claim_b = self.coordinator.claim_next_task("worker-b")
        self.assertIsNotNone(claim_a)
        self.assertIsNotNone(claim_b)
        assert claim_a is not None and claim_b is not None
        self.assertNotEqual(claim_a["task_id"], claim_b["task_id"])
        self.assertEqual(claim_a["candidate"], claim_b["candidate"])

        result = self.result()
        self.submit_claim_result("worker-a", claim_a, result)
        completed = self.submit_claim_result("worker-b", claim_b, result)

        self.assertEqual(completed["status"], "completed")
        self.assertFalse(completed["simulation"])
        self.assertEqual(completed["results"], [result])
        self.assertEqual(completed["verification"]["verified_task_count"], 2)
        self.assertEqual(completed["verification"]["method"], "independent_replica_agreement")
        self.assertEqual(len(completed["verification"]["worker_ids"]), 2)

    def test_replica_disagreement_fails_job(self) -> None:
        job = self.coordinator.submit_job(self.request())
        claim_a = self.coordinator.claim_next_task("worker-a")
        claim_b = self.coordinator.claim_next_task("worker-b")
        assert claim_a is not None and claim_b is not None
        self.submit_claim_result("worker-a", claim_a, self.result(similarity=91.2))
        failed = self.submit_claim_result("worker-b", claim_b, self.result(similarity=90.0))

        self.assertEqual(failed["status"], "failed")
        self.assertIn("Replica verification failed", " ".join(failed["errors"]))

    def test_unapproved_worker_cannot_register(self) -> None:
        with self.assertRaises(WorkerApprovalError):
            self.register("worker-c")

    def test_devices_lists_approved_endpoints_that_have_not_connected(self) -> None:
        coordinator = ClinicalComputeCoordinator(
            artifact_checksum="artifact-checksum",
            approved_worker_ids={"worker-a", "worker-b"},
        )
        devices = coordinator.devices()

        self.assertEqual({device["device_id"] for device in devices}, {"worker-a", "worker-b"})
        self.assertTrue(all(device["availability"] == "not connected" for device in devices))
        self.assertTrue(all(device["connected"] is False for device in devices))
        self.assertTrue(all(device["assigned_tasks"] == [] for device in devices))

    def test_devices_reports_registered_worker_connected_and_expected_endpoint_pending(self) -> None:
        coordinator = ClinicalComputeCoordinator(
            artifact_checksum="artifact-checksum",
            approved_worker_ids={"worker-a", "worker-b"},
        )
        coordinator.register_worker(
            ComputeWorkerRegistrationRequest(
                worker_id="worker-a",
                hostname="laptop-a.local",
                platform="test-platform",
                capabilities={
                    "workload_versions": ["trial2vec-comparison-v1"],
                    "artifact_checksum": "artifact-checksum",
                    "cpu_count": 4,
                    "memory_gb": 8,
                },
            )
        )
        devices = coordinator.devices()
        by_id = {device["device_id"]: device for device in devices}

        self.assertEqual(by_id["worker-a"]["connected"], True)
        self.assertEqual(by_id["worker-a"]["availability"], "available")
        self.assertEqual(by_id["worker-a"]["name"], "laptop-a.local")
        self.assertEqual(by_id["worker-a"]["cpu_cores"], 4)
        self.assertEqual(by_id["worker-b"]["connected"], False)
        self.assertEqual(by_id["worker-b"]["availability"], "not connected")

    def test_two_host_mode_reports_not_ready_for_workers_on_same_host(self) -> None:
        coordinator = ClinicalComputeCoordinator(
            artifact_checksum="artifact-checksum",
            approved_worker_ids={"worker-a", "worker-b"},
            require_distinct_hosts=True,
        )
        for worker_id in ("worker-a", "worker-b"):
            coordinator.register_worker(
                ComputeWorkerRegistrationRequest(
                    worker_id=worker_id,
                    hostname="same-laptop.local",
                    platform="test-platform",
                    capabilities={
                        "workload_versions": ["trial2vec-comparison-v1"],
                        "artifact_checksum": "artifact-checksum",
                    },
                )
            )

        readiness = coordinator.readiness()

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["distinct_active_host_count"], 1)
        self.assertIn("distinct active hostnames", " ".join(readiness["blockers"]))

    def test_two_host_mode_assigns_replicas_to_distinct_hosts(self) -> None:
        coordinator = ClinicalComputeCoordinator(
            artifact_checksum="artifact-checksum",
            approved_worker_ids={"worker-a", "worker-b"},
            require_distinct_hosts=True,
        )
        for worker_id, hostname in (("worker-a", "laptop-a.local"), ("worker-b", "laptop-b.local")):
            coordinator.register_worker(
                ComputeWorkerRegistrationRequest(
                    worker_id=worker_id,
                    hostname=hostname,
                    platform="test-platform",
                    capabilities={
                        "workload_versions": ["trial2vec-comparison-v1"],
                        "artifact_checksum": "artifact-checksum",
                    },
                )
            )
        coordinator.submit_job(self.request())

        claim_a = coordinator.claim_next_task("worker-a")
        claim_b = coordinator.claim_next_task("worker-b")

        self.assertTrue(coordinator.readiness()["ready"])
        self.assertIsNotNone(claim_a)
        self.assertIsNotNone(claim_b)


if __name__ == "__main__":
    unittest.main()