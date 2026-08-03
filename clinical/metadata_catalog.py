"""Read the locally generated NCT-keyed ClinicalTrials.gov metadata catalog."""

import json
from pathlib import Path


class TrialMetadataCatalog:
    def __init__(self, catalog_path: Path) -> None:
        payload = json.loads(catalog_path.read_text())
        self._records: dict[str, dict] = payload.get("records", {})

    def get(self, nct_id: str) -> dict | None:
        return self._records.get(nct_id)