"""API tests for the Phase 1 clinical evidence endpoint."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from clinical.api import create_app


class TestClinicalApi(unittest.TestCase):
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

    def test_returns_comparable_trials(self):
        response = self.client.get("/trials/NCT001/comparables?limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["nct_id"], "NCT002")
        self.assertEqual(response.json()[0]["source_workbook"], "b.xlsx")
        self.assertEqual(response.json()[0]["source"]["source_location"], "clinical/data/Emde/b.xlsx")
        self.assertTrue(response.json()[0]["source"]["content_hash_sha256"])
        self.assertTrue(response.json()[0]["metadata_available"])
        self.assertEqual(response.json()[0]["metadata"]["study_type"], "INTERVENTIONAL")

    def test_serves_demo_workspace(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Protocol prediction workspace", response.text)

    def test_applies_metadata_filters(self):
        response = self.client.get("/trials/NCT001/comparables?condition=rare%20disease&phase=phase%202")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([record["nct_id"] for record in response.json()], ["NCT002"])

    def test_reports_missing_metadata(self):
        client = TestClient(
            create_app(
                Path(self.temporary_directory.name) / "trials.npz",
                Path(self.temporary_directory.name) / "sources",
                Path(self.temporary_directory.name) / "missing-metadata.json",
            )
        )

        response = client.get("/trials/NCT001/comparables?limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()[0]["metadata_available"])
        self.assertIsNone(response.json()[0]["metadata"])

    def test_returns_not_found_for_unknown_trial(self):
        response = self.client.get("/trials/NCT404/comparables")

        self.assertEqual(response.status_code, 404)

    def test_validates_and_fingerprints_program_profile(self):
        request = {
            "profile": {
                "indication": "Rare disease",
                "endpoints": ["Functional outcome"],
                "trial_phase": "Phase 2",
            },
            "anchor_nct_id": "NCT001",
            "evidence_scope": {"source_workbooks": ["a.xlsx"]},
        }

        first_response = self.client.post("/analysis-requests/validate", json=request)
        second_response = self.client.post("/analysis-requests/validate", json=request)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["indication"], "Rare disease")
        self.assertEqual(
            first_response.json()["input_hash_sha256"],
            second_response.json()["input_hash_sha256"],
        )

    def test_creates_deterministic_evidence_brief(self):
        request = {
            "profile": {"indication": "Rare disease", "trial_phase": "Phase 2"},
            "anchor_nct_id": "NCT001",
            "limit": 1,
        }

        first_response = self.client.post("/analysis-requests/brief", json=request)
        second_response = self.client.post("/analysis-requests/brief", json=request)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json(), second_response.json())
        self.assertEqual(first_response.json()["retrieval"]["results"][0]["nct_id"], "NCT002")
        self.assertTrue(first_response.json()["retrieval"]["results"][0]["metadata_available"])
        self.assertIn("not clinical or regulatory conclusions", first_response.json()["limitations"][1])

    def test_rejects_brief_with_multiple_source_workbooks(self):
        response = self.client.post(
            "/analysis-requests/brief",
            json={
                "profile": {"indication": "Rare disease"},
                "anchor_nct_id": "NCT001",
                "evidence_scope": {"source_workbooks": ["a.xlsx", "b.xlsx"]},
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_verifies_exact_metadata_reference(self):
        response = self.client.post(
            "/claims/verify",
            json={
                "analysis_request": {
                    "profile": {"indication": "Rare disease"},
                    "anchor_nct_id": "NCT001",
                    "limit": 1,
                    "evidence_scope": {"study_type": "INTERVENTIONAL"},
                },
                "claim_id": "claim-1",
                "claim_text": "The record is titled Example study.",
                "claim_type": "trial_title",
                "reference": {
                    "nct_id": "NCT002",
                    "source_id": "clinicaltrials.gov:NCT002",
                    "content_hash_sha256": "metadata-hash",
                    "field_path": "/official_title",
                    "excerpt": "Example study",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification_status"], "source_verified")
        self.assertEqual(response.json()["rejection_reasons"], [])

    def test_rejects_claim_with_mismatched_hash(self):
        response = self.client.post(
            "/claims/verify",
            json={
                "analysis_request": {
                    "profile": {"indication": "Rare disease"},
                    "anchor_nct_id": "NCT001",
                    "limit": 1,
                    "evidence_scope": {"study_type": "INTERVENTIONAL"},
                },
                "claim_id": "claim-1",
                "claim_text": "The record is titled Example study.",
                "claim_type": "trial_title",
                "reference": {
                    "nct_id": "NCT002",
                    "source_id": "clinicaltrials.gov:NCT002",
                    "content_hash_sha256": "wrong-hash",
                    "field_path": "/official_title",
                    "excerpt": "Example study",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verification_status"], "rejected")
        self.assertEqual(response.json()["rejection_reasons"], ["content_hash_mismatch"])

    def test_analyzes_protocol_draft_without_success_prediction(self):
        response = self.client.post(
            "/protocol-drafts/analyze",
            json={
                "draft": {
                    "protocol_text": "Updated protocol draft.",
                    "indication": "Rare disease",
                    "study_phase": "Phase 2",
                    "population": "Adults",
                    "intervention": "Example therapy",
                    "primary_endpoint": "Functional outcome",
                    "planned_enrollment": 80,
                },
                "previous_draft": {
                    "protocol_text": "Original protocol draft.",
                    "indication": "Rare disease",
                    "study_phase": "Phase 2",
                    "population": "Adults",
                    "intervention": "Example therapy",
                    "primary_endpoint": "Functional outcome",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["prediction"]["available"])
        self.assertIn("comparator", response.json()["coverage"]["missing_design_fields"])
        self.assertIn("planned_enrollment", response.json()["change_signals"]["added_fields"])
        self.assertNotIn("probability", response.json()["prediction"])

    def test_runs_simulated_trial2vec_prediction_job_to_completion(self):
        created = self.client.post(
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

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["status"], "submitted")
        self.assertTrue(created.json()["simulation"])
        self.assertEqual(created.json()["results"][0]["similar_historical_trials"][0]["nct_id"], "NCT002")
        self.assertIn("not a validated", created.json()["results"][0]["score_label"])
        self.assertGreater(created.json()["results"][0]["experimental_demo_estimate"], 50)

        jobs = self.client.get("/demo/prediction-jobs/history")
        self.assertEqual(jobs.status_code, 200)
        self.assertEqual(jobs.json()[0]["job_id"], created.json()["job_id"])
        self.assertEqual(jobs.json()[0]["status"], "submitted")

        job_id = created.json()["job_id"]
        for _ in range(6):
            completed = self.client.post(f"/demo/prediction-jobs/{job_id}/advance")

        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "completed")
        self.assertEqual(completed.json()["tasks"][0]["status"], "completed")

        devices = self.client.get("/demo/devices")
        self.assertEqual(devices.status_code, 200)
        self.assertTrue(devices.json()[0]["approved"])

    def test_approves_and_finalizes_reviewable_brief(self):
        created = self.client.post("/reviewable-briefs", json=self.reviewable_brief_request()).json()

        review = self.client.post(
            f"/reviewable-briefs/{created['brief_id']}/claims/claim-1/reviews",
            json={"reviewer_id": "reviewer@example.com", "decision": "approved"},
        )
        finalized = self.client.post(f"/reviewable-briefs/{created['brief_id']}/finalize")
        exported = self.client.get(f"/reviewable-briefs/{created['brief_id']}/export.md")
        post_finalization_review = self.client.post(
            f"/reviewable-briefs/{created['brief_id']}/claims/claim-1/reviews",
            json={"reviewer_id": "reviewer@example.com", "decision": "rejected"},
        )

        self.assertEqual(review.status_code, 200)
        self.assertEqual(finalized.status_code, 200)
        self.assertEqual(finalized.json()["status"], "finalized")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("clinicaltrials.gov:NCT002", exported.text)
        self.assertIn("metadata-hash", exported.text)
        self.assertEqual(post_finalization_review.status_code, 409)

    def test_rejected_claim_blocks_finalization(self):
        created = self.client.post("/reviewable-briefs", json=self.reviewable_brief_request()).json()
        self.client.post(
            f"/reviewable-briefs/{created['brief_id']}/claims/claim-1/reviews",
            json={"reviewer_id": "reviewer@example.com", "decision": "rejected"},
        )

        response = self.client.post(f"/reviewable-briefs/{created['brief_id']}/finalize")

        self.assertEqual(response.status_code, 422)

    @staticmethod
    def reviewable_brief_request():
        return {
            "analysis_request": {
                "profile": {"indication": "Rare disease"},
                "anchor_nct_id": "NCT001",
                "limit": 1,
                "evidence_scope": {"study_type": "INTERVENTIONAL"},
            },
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim_text": "The record is titled Example study.",
                    "claim_type": "trial_title",
                    "reference": {
                        "nct_id": "NCT002",
                        "source_id": "clinicaltrials.gov:NCT002",
                        "content_hash_sha256": "metadata-hash",
                        "field_path": "/official_title",
                        "excerpt": "Example study",
                    },
                }
            ],
            }

    def test_rejects_profile_without_indication(self):
        response = self.client.post(
            "/analysis-requests/validate",
            json={"profile": {}, "anchor_nct_id": "NCT001"},
        )

        self.assertEqual(response.status_code, 422)

    def test_returns_curated_anchor_trials(self):
        response = self.client.get("/demo/anchors?limit=10")

        self.assertEqual(response.status_code, 200)
        anchors = response.json()
        nct_ids = [anchor["nct_id"] for anchor in anchors]
        self.assertIn("NCT001", nct_ids)
        self.assertIn("NCT002", nct_ids)
        by_id = {anchor["nct_id"]: anchor for anchor in anchors}
        self.assertFalse(by_id["NCT001"]["metadata_available"])
        self.assertIsNone(by_id["NCT001"]["title"])
        self.assertTrue(by_id["NCT002"]["metadata_available"])
        self.assertEqual(by_id["NCT002"]["title"], "Example study")
        self.assertEqual(by_id["NCT002"]["indication"], "Rare disease")
        self.assertEqual(by_id["NCT002"]["phase"], "PHASE2")

    def test_filters_anchor_trials_by_nct_id(self):
        response = self.client.get("/demo/anchors?query=NCT002")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([anchor["nct_id"] for anchor in response.json()], ["NCT002"])

    def test_filters_anchor_trials_by_metadata(self):
        response = self.client.get("/demo/anchors?query=rare%20disease")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([anchor["nct_id"] for anchor in response.json()], ["NCT002"])

    def test_limits_anchor_trials(self):
        response = self.client.get("/demo/anchors?limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_workspace_includes_accessible_status_region(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="sr-status"', response.text)
        self.assertIn('aria-live="polite"', response.text)
        self.assertIn('id="submit-job"', response.text)
        self.assertIn('aria-describedby="submit-status"', response.text)