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
        np.savez_compressed(
            dataset_path,
            nct_id=np.array(["NCT001", "NCT002"]),
            X=np.array([[1, 0], [0.9, 0.1]], dtype=np.float32),
            y=np.array([0, 1]),
            label_names=np.array(["0.0", "1.0"]),
            source_workbook=np.array(["a.xlsx", "b.xlsx"]),
        )
        self.client = TestClient(create_app(dataset_path))

    def test_returns_comparable_trials(self):
        response = self.client.get("/trials/NCT001/comparables?limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["nct_id"], "NCT002")
        self.assertEqual(response.json()[0]["source_workbook"], "b.xlsx")

    def test_returns_not_found_for_unknown_trial(self):
        response = self.client.get("/trials/NCT404/comparables")

        self.assertEqual(response.status_code, 404)