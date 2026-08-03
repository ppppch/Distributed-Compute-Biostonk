"""Tests for ClinicalTrials.gov v2 metadata catalog import."""

import json
import tempfile
import unittest
from pathlib import Path

from clinical.import_metadata import import_metadata


class TestMetadataImport(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.input_path = Path(self.temporary_directory.name) / "studies.json"
        self.output_path = Path(self.temporary_directory.name) / "metadata.json"

    def test_creates_provenance_linked_nct_record(self):
        self.input_path.write_text(
            json.dumps(
                {
                    "studies": [
                        {
                            "protocolSection": {
                                "identificationModule": {
                                    "nctId": "NCT001",
                                    "officialTitle": "Example study",
                                },
                                "designModule": {"phases": ["PHASE2"], "studyType": "INTERVENTIONAL"},
                                "conditionsModule": {"conditions": ["Rare disease"]},
                                "armsInterventionsModule": {
                                    "interventions": [{"name": "Example drug", "type": "DRUG"}]
                                },
                                "outcomesModule": {
                                    "primaryOutcomes": [{"measure": "Functional outcome"}]
                                },
                                "contactsLocationsModule": {"locations": [{"country": "United States"}]},
                            }
                        }
                    ]
                }
            )
        )

        count = import_metadata(self.input_path, self.output_path)
        catalog = json.loads(self.output_path.read_text())
        record = catalog["records"]["NCT001"]

        self.assertEqual(count, 1)
        self.assertEqual(record["phases"], ["PHASE2"])
        self.assertEqual(record["primary_outcomes"], ["Functional outcome"])
        self.assertEqual(record["source_url"], "https://clinicaltrials.gov/study/NCT001")
        self.assertTrue(record["content_hash_sha256"])

    def test_preserves_missing_optional_fields_as_null_or_empty(self):
        self.input_path.write_text(
            json.dumps({"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT002"}}}]})
        )

        import_metadata(self.input_path, self.output_path)
        record = json.loads(self.output_path.read_text())["records"]["NCT002"]

        self.assertIsNone(record["official_title"])
        self.assertEqual(record["conditions"], [])
        self.assertEqual(record["primary_outcomes"], [])