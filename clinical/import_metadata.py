"""Build an NCT-keyed metadata catalog from a ClinicalTrials.gov v2 export."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/study/"


def values(module: dict[str, Any], key: str) -> list[str]:
    return [str(value) for value in module.get(key, []) if value]


def first_value(module: dict[str, Any], key: str) -> str | None:
    value = module.get(key)
    return str(value) if value else None


def study_record(study: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    protocol = study.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    description = protocol.get("descriptionModule", {})
    conditions = protocol.get("conditionsModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})
    contacts = protocol.get("contactsLocationsModule", {})
    nct_id = first_value(identification, "nctId")
    if not nct_id:
        raise ValueError("ClinicalTrials.gov study is missing protocolSection.identificationModule.nctId")

    record = {
        "nct_id": nct_id,
        "official_title": first_value(identification, "officialTitle"),
        "brief_summary": first_value(description, "briefSummary"),
        "conditions": values(conditions, "conditions"),
        "phases": values(design, "phases"),
        "study_type": first_value(design, "studyType"),
        "interventions": [
            {
                "name": first_value(intervention, "name"),
                "type": first_value(intervention, "type"),
            }
            for intervention in arms.get("interventions", [])
        ],
        "primary_outcomes": [
            first_value(outcome, "measure")
            for outcome in outcomes.get("primaryOutcomes", [])
            if first_value(outcome, "measure")
        ],
        "secondary_outcomes": [
            first_value(outcome, "measure")
            for outcome in outcomes.get("secondaryOutcomes", [])
            if first_value(outcome, "measure")
        ],
        "sponsor": first_value(protocol.get("sponsorCollaboratorsModule", {}), "leadSponsor"),
        "overall_status": first_value(status, "overallStatus"),
        "start_date": first_value(status.get("startDateStruct", {}), "date"),
        "completion_date": first_value(status.get("completionDateStruct", {}), "date"),
        "countries": sorted(
            {
                str(location["country"])
                for location in contacts.get("locations", [])
                if location.get("country")
            }
        ),
        "source_id": f"clinicaltrials.gov:{nct_id}",
        "source_url": f"{CLINICAL_TRIALS_BASE_URL}{nct_id}",
        "retrieved_at": retrieved_at,
    }
    record["content_hash_sha256"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return record


def import_metadata(input_path: Path, output_path: Path) -> int:
    payload = json.loads(input_path.read_text())
    studies = payload.get("studies", [])
    if not isinstance(studies, list):
        raise ValueError("ClinicalTrials.gov export must contain a studies array")

    retrieved_at = datetime.now(timezone.utc).isoformat()
    records = [study_record(study, retrieved_at) for study in studies]
    records_by_id = {record["nct_id"]: record for record in records}
    if len(records_by_id) != len(records):
        raise ValueError("ClinicalTrials.gov export contains duplicate NCT IDs")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "source": "ClinicalTrials.gov API v2 export",
                "retrieved_at": retrieved_at,
                "records": records_by_id,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return len(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import a ClinicalTrials.gov v2 studies export into a metadata catalog."
    )
    parser.add_argument("input", type=Path, help="ClinicalTrials.gov v2 JSON export")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("clinical/data/trial_metadata.json"),
    )
    arguments = parser.parse_args()
    count = import_metadata(arguments.input, arguments.output)
    print(f"Saved {count:,} trial metadata records to {arguments.output}")