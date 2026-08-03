"""Tests for bounded ClinicalTrials.gov demo metadata retrieval."""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from clinical.fetch_metadata import cohort_ids, fetch_studies


class TestFetchMetadata(unittest.TestCase):
    def test_selects_sorted_unique_cohort_ids(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_path = Path(temporary_directory) / "trials.npz"
            np.savez_compressed(dataset_path, nct_id=np.array(["NCT003", "NCT001", "NCT003", "NCT002"]))

            self.assertEqual(cohort_ids(dataset_path, limit=2), ["NCT001", "NCT002"])

    def test_fetches_each_requested_study(self):
        requested_ids: list[str] = []

        def fake_fetch(nct_id: str) -> dict:
            requested_ids.append(nct_id)
            return {"id": nct_id}

        studies = fetch_studies(["NCT001", "NCT002"], fake_fetch, delay_seconds=0)

        self.assertEqual(requested_ids, ["NCT001", "NCT002"])
        self.assertEqual(studies, [{"id": "NCT001"}, {"id": "NCT002"}])