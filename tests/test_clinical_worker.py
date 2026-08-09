"""Tests for deterministic clinical worker task execution."""

import tempfile
import unittest
from unittest.mock import Mock
from pathlib import Path

import numpy as np

from client.clinical_worker import execute_claim
from clinical.distributed_compute import WORKLOAD_VERSION, canonical_checksum
from clinical.evidence_catalog import EvidenceCatalog
from clinical.schemas import PredictionCandidate
from clinical.trial_search import TrialSearch


class TestClinicalWorker(unittest.TestCase):
    def test_executes_claim_and_hashes_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source_directory = directory / "sources"
            source_directory.mkdir()
            (source_directory / "a.xlsx").write_bytes(b"source-a")
            (source_directory / "b.xlsx").write_bytes(b"source-b")
            dataset_path = directory / "trials.npz"
            np.savez_compressed(
                dataset_path,
                nct_id=np.array(["NCT001", "NCT002"]),
                X=np.array([[1, 0], [0.9, 0.1]], dtype=np.float32),
                y=np.array([0, 1]),
                label_names=np.array(["0.0", "1.0"]),
                source_workbook=np.array(["a.xlsx", "b.xlsx"]),
            )
            search = TrialSearch(dataset_path, EvidenceCatalog(source_directory).source_records())
            candidate = PredictionCandidate.model_validate(
                {
                    "candidate_id": "candidate-a",
                    "anchor_nct_id": "NCT001",
                    "draft": {"protocol_text": "Protocol A"},
                }
            )
            claim = {
                "job_id": "job-1",
                "task_id": "task-1",
                "workload_version": WORKLOAD_VERSION,
                "artifact_checksum": "artifact-checksum",
                "candidate": candidate.model_dump(mode="json"),
            }

            payload = execute_claim(claim, "worker-a", search, "artifact-checksum")

            self.assertTrue(payload["success"])
            self.assertEqual(payload["result"]["candidate_id"], "candidate-a")
            self.assertEqual(payload["checksum"], canonical_checksum(payload["result"]))

    def test_rejects_task_for_different_dataset(self) -> None:
        claim = {
            "job_id": "job-1",
            "task_id": "task-1",
            "workload_version": WORKLOAD_VERSION,
            "artifact_checksum": "coordinator-artifacts",
            "candidate": {},
        }

        payload = execute_claim(claim, "worker-a", Mock(), "worker-artifacts")

        self.assertFalse(payload["success"])
        self.assertIn("artifact checksum", payload["error"])


if __name__ == "__main__":
    unittest.main()