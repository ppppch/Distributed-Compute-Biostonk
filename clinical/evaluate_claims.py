"""Evaluate source-reference verification against reviewer-authored examples."""

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from clinical.claim_verifier import verify_claim
from clinical.evidence_catalog import EvidenceCatalog
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.schemas import ClaimEvaluationExample
from clinical.trial_search import TrialSearch


def load_examples(input_path: Path) -> list[ClaimEvaluationExample]:
    payload = json.loads(input_path.read_text())
    examples = payload.get("examples", [])
    if not isinstance(examples, list):
        raise ValueError("evaluation input must contain an examples array")
    return [ClaimEvaluationExample.model_validate(example) for example in examples]


def evaluate_examples(
    examples: list[ClaimEvaluationExample],
    search: TrialSearch,
) -> dict[str, Any]:
    """Return deterministic verification and reviewer-label metrics."""
    expected_verified_count = 0
    actual_verified_count = 0
    true_positive_count = 0
    mismatches = []
    source_support_counts: Counter[str] = Counter()
    applicability_counts: Counter[str] = Counter()
    evidence_gap_claim_ids = []

    for example in examples:
        result = verify_claim(example.verification_request, search)
        expected_status = example.expected_verification_status
        actual_status = result["verification_status"]
        if expected_status == "source_verified":
            expected_verified_count += 1
        if actual_status == "source_verified":
            actual_verified_count += 1
        if expected_status == actual_status == "source_verified":
            true_positive_count += 1
        if expected_status != actual_status:
            mismatches.append(
                {
                    "claim_id": example.verification_request.claim_id,
                    "expected_verification_status": expected_status,
                    "actual_verification_status": actual_status,
                    "rejection_reasons": result["rejection_reasons"],
                }
            )
        source_support_counts[example.review.source_support] += 1
        applicability_counts[example.review.applicability] += 1
        if example.review.source_support != "supported" or example.review.applicability != "applicable":
            evidence_gap_claim_ids.append(example.verification_request.claim_id)

    return {
        "total_examples": len(examples),
        "expected_verified_count": expected_verified_count,
        "actual_verified_count": actual_verified_count,
        "true_positive_count": true_positive_count,
        "source_reference_precision": ratio(true_positive_count, actual_verified_count),
        "source_reference_recall": ratio(true_positive_count, expected_verified_count),
        "verification_mismatches": mismatches,
        "reviewer_labels": {
            "source_support_counts": dict(sorted(source_support_counts.items())),
            "applicability_counts": dict(sorted(applicability_counts.items())),
            "evidence_gap_claim_ids": evidence_gap_claim_ids,
        },
        "limitations": [
            "Source-reference metrics measure verifier behavior, not clinical or regulatory correctness.",
            "Reviewer labels must be supplied by qualified reviewers and are not inferred by this tool.",
        ],
    }


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate BioStonk claim source references.")
    parser.add_argument("input", type=Path, help="Reviewer-authored evaluation JSON")
    parser.add_argument("--dataset", type=Path, default=Path("clinical/data/trials.npz"))
    parser.add_argument("--sources", type=Path, default=Path("clinical/data/Emde"))
    parser.add_argument("--metadata", type=Path, default=Path("clinical/data/trial_metadata.json"))
    arguments = parser.parse_args()

    catalog = EvidenceCatalog(arguments.sources)
    metadata_catalog = TrialMetadataCatalog(arguments.metadata) if arguments.metadata.exists() else None
    search = TrialSearch(arguments.dataset, catalog.source_records(), metadata_catalog)
    print(json.dumps(evaluate_examples(load_examples(arguments.input), search), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()