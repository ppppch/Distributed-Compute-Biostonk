"""Integration test for the full local distributed pipeline."""

import os
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _run(self, cmd, cwd):
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result

    def test_full_pipeline_matches_baseline(self):
        # Phase 1: baseline
        self._run([sys.executable, os.path.join(PROJECT_ROOT, "prepare_dataset.py")], self.tmpdir.name)
        self._run([sys.executable, os.path.join(PROJECT_ROOT, "train_model.py")], self.tmpdir.name)
        self._run([sys.executable, os.path.join(PROJECT_ROOT, "run_baseline.py")], self.tmpdir.name)

        # Phase 2: distributed workers (using refactored single worker script)
        self._run([sys.executable, os.path.join(PROJECT_ROOT, "split_job.py")], self.tmpdir.name)
        self._run([
            sys.executable,
            os.path.join(PROJECT_ROOT, "run_worker.py"),
            "job_part1.npz", "results_part1.npz", "--label", "Part 1",
        ], self.tmpdir.name)
        self._run([
            sys.executable,
            os.path.join(PROJECT_ROOT, "run_worker.py"),
            "job_part2.npz", "results_part2.npz", "--label", "Part 2",
        ], self.tmpdir.name)

        # Phase 3: combine and verify
        result = self._run(
            [sys.executable, os.path.join(PROJECT_ROOT, "combine_and_verify.py")],
            self.tmpdir.name,
        )

        self.assertIn("MATCH - distributed results are identical to the baseline.", result.stdout)


if __name__ == "__main__":
    unittest.main()
