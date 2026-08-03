"""Tests for source-backed reviewer packet generation."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from clinical.evidence_catalog import EvidenceCatalog
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.review_packet import build_review_packet
from clinical.schemas import ComparableProgramRequest
from clinical.trial_search import TrialSearch


class TestReviewPacket(unittest.TestCase):
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
        np.savez_compressed(
            dataset_path,
            nct_id=np.array(["NCT001", "NCT002"]),
            X=np.array([[1, 0], [0.9, 0.1]], dtype=np.float32),
            y=np.array([0, 1]),
            label_names=np.array(["0.0", "1.0"]),
            source_workbook=np.array(["a.xlsx", "b.xlsx"]),
        )
        metadata_path.write_text(
            '{"records":{"NCT002":{"nct_id":"NCT002","source_id":"clinicaltrials.gov:NCT002","source_url":"https://clinicaltrials.gov/study/NCT002","content_hash_sha256":"metadata-hash","official_title":"Example study","conditions":["Rare disease"],"study_type":"INTERVENTIONAL"}}}'
        )
        catalog = EvidenceCatalog(sources)
        self.search = TrialSearch(dataset_path, catalog.source_records(), TrialMetadataCatalog(metadata_path))

    def test_builds_reviewer_packet_with_verbatim_references(self):
        request = ComparableProgramRequest.model_validate(
            {
                "profile": {"indication": "Rare disease"},
                "anchor_nct_id": "NCT001",
                "limit": 1,
                "evidence_scope": {"study_type": "INTERVENTIONAL"},
            }
        )

        packet = build_review_packet(request, self.search)

        self.assertEqual(packet["candidate_sources"][0]["nct_id"], "NCT002")
        self.assertEqual(packet["candidate_sources"][0]["content_hash_sha256"], "metadata-hash")
        self.assertIn(
            {"field_path": "/official_title", "excerpt": "Example study"},
            packet["candidate_sources"][0]["candidate_references"],
        )
        self.assertNotIn(
            {"field_path": "/content_hash_sha256", "excerpt": "metadata-hash"},
            packet["candidate_sources"][0]["candidate_references"],
        )