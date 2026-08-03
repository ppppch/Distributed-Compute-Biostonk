"""Tests for reviewer-authored claim evaluation metrics."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from clinical.evidence_catalog import EvidenceCatalog
from clinical.evaluate_claims import evaluate_examples, load_examples
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.trial_search import TrialSearch


class TestEvaluateClaims(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        directory = Path(self.temporary_directory.name)
        sources = directory / "sources"
        sources.mkdir()
        (sources / "a.xlsx").write_bytes(b"source-a")
        (sources / "b.xlsx").write_bytes(b"source-b")
        dataset_path = directory / "trials.npz"
        metadata_path = directory / "metadata.json"
        self.evaluation_path = directory / "evaluation.json"
        np.savez_compressed(
            dataset_path,
            nct_id=np.array(["NCT001", "NCT002"]),
            X=np.array([[1, 0], [0.9, 0.1]], dtype=np.float32),
            y=np.array([0, 1]),
            label_names=np.array(["0.0", "1.0"]),
            source_workbook=np.array(["a.xlsx", "b.xlsx"]),
        )
        metadata_path.write_text(
            '{"records":{"NCT002":{"source_id":"clinicaltrials.gov:NCT002","content_hash_sha256":"metadata-hash","official_title":"Example study","study_type":"INTERVENTIONAL"}}}'
        )
        catalog = EvidenceCatalog(sources)
        self.search = TrialSearch(dataset_path, catalog.source_records(), TrialMetadataCatalog(metadata_path))

    def test_reports_verification_and_reviewer_metrics(self):
        self.evaluation_path.write_text(json.dumps({"examples": [self.example("metadata-hash", "source_verified", "supported", "applicable"), self.example("wrong-hash", "rejected", "unsupported", "not_applicable")]}))

        results = evaluate_examples(load_examples(self.evaluation_path), self.search)

        self.assertEqual(results["total_examples"], 2)
        self.assertEqual(results["source_reference_precision"], 1.0)
        self.assertEqual(results["source_reference_recall"], 1.0)
        self.assertEqual(results["verification_mismatches"], [])
        self.assertEqual(results["reviewer_labels"]["evidence_gap_claim_ids"], ["claim-wrong-hash"])

    @staticmethod
    def example(hash_value, expected_status, source_support, applicability):
        return {
            "verification_request": {
                "analysis_request": {
                    "profile": {"indication": "Rare disease"},
                    "anchor_nct_id": "NCT001",
                    "limit": 1,
                    "evidence_scope": {"study_type": "INTERVENTIONAL"},
                },
                "claim_id": f"claim-{hash_value}",
                "claim_text": "The record is titled Example study.",
                "claim_type": "trial_title",
                "reference": {
                    "nct_id": "NCT002",
                    "source_id": "clinicaltrials.gov:NCT002",
                    "content_hash_sha256": hash_value,
                    "field_path": "/official_title",
                    "excerpt": "Example study",
                },
            },
            "expected_verification_status": expected_status,
            "review": {
                "reviewer_id": "qualified-reviewer",
                "reviewed_at": "2026-08-03T00:00:00+00:00",
                "source_support": source_support,
                "applicability": applicability,
            },
        }