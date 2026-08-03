"""Tests for clinical trial similarity retrieval."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from clinical.evidence_catalog import EvidenceSource
from clinical.trial_search import TrialSearch


class TestTrialSearch(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.dataset_path = Path(self.temporary_directory.name) / "trials.npz"
        np.savez_compressed(
            self.dataset_path,
            nct_id=np.array(["NCT001", "NCT002", "NCT003"]),
            X=np.array([[1, 0], [0.9, 0.1], [0, 1]], dtype=np.float32),
            y=np.array([0, 0, 1]),
            label_names=np.array(["0.0", "1.0"]),
            source_workbook=np.array(["a.xlsx", "a.xlsx", "b.xlsx"]),
        )
        self.search = TrialSearch(
            self.dataset_path,
            {
                "a.xlsx": EvidenceSource("source-a", "test", "a.xlsx", "hash-a", "2026-01-01T00:00:00+00:00"),
                "b.xlsx": EvidenceSource("source-b", "test", "b.xlsx", "hash-b", "2026-01-01T00:00:00+00:00"),
            },
        )

    def test_returns_closest_trial_with_provenance(self):
        results = self.search.find_comparables("NCT001", limit=1)

        self.assertEqual(results[0].nct_id, "NCT002")
        self.assertEqual(results[0].sentiment, "0.0")
        self.assertEqual(results[0].source_workbook, "a.xlsx")
        self.assertEqual(results[0].source.source_id, "source-a")
        self.assertGreater(results[0].similarity, 0.9)

    def test_applies_source_and_sentiment_filters(self):
        results = self.search.find_comparables(
            "NCT001", source_workbook="b.xlsx", sentiment="1.0"
        )

        self.assertEqual([result.nct_id for result in results], ["NCT003"])

    def test_rejects_unknown_trial_identifier(self):
        with self.assertRaises(KeyError):
            self.search.find_comparables("NCT404")


if __name__ == "__main__":
    unittest.main()