"""Unit tests for run_worker.py."""

import os
import tempfile
import unittest

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

import run_worker


class TestRunWorker(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        # Tiny deterministic model so we can predict without large data.
        X = np.array([[0, 0], [1, 1], [0, 1], [1, 0]])
        y = np.array([0, 1, 1, 0])
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)

        self.model_path = os.path.join(self.tmpdir.name, "model.joblib")
        joblib.dump(model, self.model_path)

        self.input_path = os.path.join(self.tmpdir.name, "chunk.npz")
        np.savez(
            self.input_path,
            X=np.array([[0, 0], [1, 1]]),
            original_index=np.array([5, 2]),
        )

        self.output_path = os.path.join(self.tmpdir.name, "out.npz")

    def test_run_worker_returns_sample_count(self):
        n = run_worker.run_worker(self.input_path, self.output_path, self.model_path)
        self.assertEqual(n, 2)

    def test_run_worker_writes_predictions_and_indices(self):
        run_worker.run_worker(self.input_path, self.output_path, self.model_path)

        self.assertTrue(os.path.exists(self.output_path))
        out = np.load(self.output_path)

        self.assertIn("predictions", out.files)
        self.assertIn("original_index", out.files)
        self.assertEqual(out["predictions"].shape[0], 2)
        np.testing.assert_array_equal(out["original_index"], np.array([5, 2]))

    def test_run_worker_preserves_original_index_order(self):
        run_worker.run_worker(self.input_path, self.output_path, self.model_path)
        out = np.load(self.output_path)
        np.testing.assert_array_equal(out["original_index"], np.array([5, 2]))


class TestRunWorkerCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(np.array([[0, 0], [1, 1]]), np.array([0, 1]))

        self.model_path = os.path.join(self.tmpdir.name, "model.joblib")
        joblib.dump(model, self.model_path)

        self.input_path = os.path.join(self.tmpdir.name, "chunk.npz")
        np.savez(
            self.input_path,
            X=np.array([[0, 0]]),
            original_index=np.array([7]),
        )

        self.output_path = os.path.join(self.tmpdir.name, "out.npz")

    def test_main_runs_with_argv(self):
        argv = [
            self.input_path,
            self.output_path,
            "--model", self.model_path,
            "--label", "TestWorker",
        ]
        run_worker.main(argv)

        self.assertTrue(os.path.exists(self.output_path))
        out = np.load(self.output_path)
        np.testing.assert_array_equal(out["original_index"], np.array([7]))


if __name__ == "__main__":
    unittest.main()
