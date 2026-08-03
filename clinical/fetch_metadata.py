"""Fetch a bounded ClinicalTrials.gov v2 export for a local demo cohort."""

import argparse
import json
from pathlib import Path
import time
from typing import Callable
from urllib.request import urlopen

import numpy as np


STUDY_URL = "https://clinicaltrials.gov/api/v2/studies/{nct_id}"


def fetch_studies(
    nct_ids: list[str],
    fetch: Callable[[str], dict],
    delay_seconds: float = 0.1,
) -> list[dict]:
    """Fetch studies one at a time, keeping API traffic bounded and auditable."""
    studies: list[dict] = []
    for index, nct_id in enumerate(nct_ids):
        studies.append(fetch(nct_id))
        if index < len(nct_ids) - 1:
            time.sleep(delay_seconds)
    return studies


def clinicaltrials_fetch(nct_id: str) -> dict:
    with urlopen(STUDY_URL.format(nct_id=nct_id), timeout=30) as response:
        return json.loads(response.read())


def cohort_ids(dataset_path: Path, limit: int) -> list[str]:
    dataset = np.load(dataset_path)
    nct_ids = sorted(set(dataset["nct_id"].astype(str).tolist()))
    return nct_ids[:limit]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch a bounded ClinicalTrials.gov v2 study export for the demo."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("clinical/data/trials.npz"),
    )
    parser.add_argument("--output", type=Path, default=Path("clinical/data/studies.json"))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay-seconds", type=float, default=0.1)
    arguments = parser.parse_args()
    if arguments.limit < 1 or arguments.limit > 100:
        parser.error("--limit must be between 1 and 100 for the demo cohort")

    nct_ids = cohort_ids(arguments.dataset, arguments.limit)
    studies = fetch_studies(nct_ids, clinicaltrials_fetch, arguments.delay_seconds)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps({"studies": studies}, indent=2) + "\n")
    print(f"Saved {len(studies)} ClinicalTrials.gov studies to {arguments.output}")