import unittest
import numpy as np
from clinical.import_trials import validate_npz_schema

class TestImportTrialsValidation(unittest.TestCase):

    def test_valid_schema(self):
        """Test schema validation succeeds with all required keys."""
        payload = {
            "nct_id": np.array(["NCT00000001"]),
            "label_names": np.array(["0.0", "1.0"]),
            "source_workbook": np.array(["test.xlsx"]),
            "X": np.zeros((1, 128))
        }
        is_valid, msg = validate_npz_schema(payload)
        self.assertTrue(is_valid)
        self.assertEqual(msg, "Schema validation passed.")

    def test_missing_required_keys(self):
        """Test schema validation catches missing required metadata keys."""
        payload = {
            "nct_id": np.array(["NCT00000001"]),
            # "source_workbook" is missing
            "label_names": np.array(["0.0"])
        }
        is_valid, msg = validate_npz_schema(payload)
        self.assertFalse(is_valid)
        self.assertIn("Missing required keys", msg)

    def test_empty_dataset_validation(self):
        """Test schema validation catches empty array payloads."""
        payload = {
            "nct_id": np.array([]),
            "label_names": np.array([]),
            "source_workbook": np.array([])
        }
        is_valid, msg = validate_npz_schema(payload)
        self.assertFalse(is_valid)
        self.assertIn("dataset is empty", msg)

if __name__ == "__main__":
    unittest.main()
