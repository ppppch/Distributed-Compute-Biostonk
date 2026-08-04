"""Focused lifecycle tests for simulated distributed prediction jobs."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from clinical.api import create_app


class TestPredictionJobLifecycle(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        dataset_path = Path(self.temporary_directory.name) / "trials.npz"
        source_directory = Path(self.temporary_directory.name) / "sources"
        metadata_path = Path(self.temporary_directory.name) / "metadata.json"
        review_store_path = Path(self.temporary_directory.name) / "reviewed_briefs.json"
        source_directory.mkdir()
        (source_directory / "a.xlsx").write_bytes(b"source-a")
        (source_directory / "b.xlsx").write_bytes(b"source-b")
        metadata_path.write_text(
            '{"records":{"NCT002":{"source_id":"clinicaltrials.gov:NCT002","source_url":"https://clinicaltrials.gov/study/NCT002","content_hash_sha256":"metadata-hash","official_title":"Example study","conditions":["Rare disease"],"phases":["PHASE2"],"study_type":"INTERVENTIONAL","enrollment":80,"overall_status":"COMPLETED","interventions":[{"type":"DRUG"}]}}}'
        )
        np.savez_compressed(
            dataset_path,
            nct_id=np.array(["NCT001", "NCT002"]),
            X=np.array([[1, 0], [0.9, 0.1]], dtype=np.float32),
            y=np.array([0, 1]),
            label_names=np.array(["0.0", "1.0"]),
            source_workbook=np.array(["a.xlsx", "b.xlsx"]),
        )
        self.client = TestClient(create_app(dataset_path, source_directory, metadata_path, review_store_path))

    def _create_job(self):
        response = self.client.post(
            "/demo/prediction-jobs",
            json={
                "candidates": [
                    {
                        "candidate_id": "candidate-a",
                        "anchor_nct_id": "NCT001",
                        "draft": {
                            "protocol_text": "Protocol candidate A",
                            "indication": "Rare disease",
                            "study_phase": "PHASE2",
                            "population": "Adults",
                            "intervention": "Example drug",
                            "intervention_type": "DRUG",
                            "comparator": "Standard care",
                            "primary_endpoint": "Functional outcome",
                            "planned_enrollment": 80,
                            "planned_site_count": 4,
                        },
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_new_job_starts_in_submitted_state(self):
        job = self._create_job()

        self.assertEqual(job["status"], "submitted")
        self.assertEqual(
            job["lifecycle"],
            ["submitted", "sharded", "distributed", "running", "verified", "aggregated", "completed"],
        )

    def test_advance_moves_through_lifecycle_in_order(self):
        job = self._create_job()
        job_id = job["job_id"]
        expected_states = ["sharded", "distributed", "running", "verified", "aggregated", "completed"]

        for expected_state in expected_states:
            response = self.client.post(f"/demo/prediction-jobs/{job_id}/advance")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], expected_state)

        final_response = self.client.get(f"/demo/prediction-jobs/{job_id}")
        self.assertEqual(final_response.status_code, 200)
        final_job = final_response.json()
        self.assertEqual(final_job["status"], "completed")
        self.assertTrue(all(task["status"] == "completed" for task in final_job["tasks"]))

    def test_advance_on_completed_job_returns_completed_without_error(self):
        job = self._create_job()
        job_id = job["job_id"]
        for _ in range(len(job["lifecycle"]) - 1):
            self.client.post(f"/demo/prediction-jobs/{job_id}/advance")

        first_extra = self.client.post(f"/demo/prediction-jobs/{job_id}/advance")
        self.assertEqual(first_extra.status_code, 200)
        self.assertEqual(first_extra.json()["status"], "completed")

        second_extra = self.client.post(f"/demo/prediction-jobs/{job_id}/advance")
        self.assertEqual(second_extra.status_code, 200)
        self.assertEqual(second_extra.json()["status"], "completed")

    def test_unknown_job_id_returns_404(self):
        unknown_id = "demo-nonexistent99"

        advance_response = self.client.post(f"/demo/prediction-jobs/{unknown_id}/advance")
        self.assertEqual(advance_response.status_code, 404)
        self.assertIn("Unknown demo job ID", advance_response.json()["detail"])

        get_response = self.client.get(f"/demo/prediction-jobs/{unknown_id}")
        self.assertEqual(get_response.status_code, 404)
        self.assertIn("Unknown demo job ID", get_response.json()["detail"])

    def test_history_distinguishes_in_progress_and_completed_jobs(self):
        in_progress_job = self._create_job()

        completed_job = self._create_job()
        for _ in range(len(completed_job["lifecycle"]) - 1):
            self.client.post(f"/demo/prediction-jobs/{completed_job['job_id']}/advance")

        history_response = self.client.get("/demo/prediction-jobs/history")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()

        self.assertEqual(len(history), 2)
        statuses_by_id = {job["job_id"]: job["status"] for job in history}
        self.assertEqual(statuses_by_id[in_progress_job["job_id"]], "submitted")
        self.assertEqual(statuses_by_id[completed_job["job_id"]], "completed")


if __name__ == "__main__":
    unittest.main()
