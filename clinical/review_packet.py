"""Prepare source-backed reviewer packets without generating claim content."""

import argparse
import json
from pathlib import Path
from typing import Any

from clinical.evidence_brief import build_evidence_brief
from clinical.evidence_catalog import EvidenceCatalog
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.schemas import ComparableProgramRequest
from clinical.trial_search import TrialSearch


PACKET_VERSION = "phase1-review-packet-v1"
EXCLUDED_METADATA_FIELDS = {"content_hash_sha256", "nct_id", "retrieved_at", "source_id", "source_url"}


def build_review_packet(
    request: ComparableProgramRequest,
    search: TrialSearch,
) -> dict[str, Any]:
    """Return candidate excerpts for qualified reviewers to label manually."""
    evidence_brief = build_evidence_brief(request, search)
    candidates = []
    for result in evidence_brief["retrieval"]["results"]:
        metadata = result["metadata"]
        if metadata is None:
            continue
        candidates.append(
            {
                "nct_id": result["nct_id"],
                "source_id": metadata["source_id"],
                "source_url": metadata["source_url"],
                "content_hash_sha256": metadata["content_hash_sha256"],
                "candidate_references": metadata_references(metadata),
            }
        )
    return {
        "packet_version": PACKET_VERSION,
        "analysis_input_hash_sha256": request.input_hash(),
        "anchor_nct_id": request.anchor_nct_id,
        "candidate_sources": candidates,
        "evidence_gaps": evidence_brief["evidence_gaps"],
        "review_instructions": [
            "Create claims and labels manually; this packet does not generate claims or clinical conclusions.",
            "Use only the supplied source ID, content hash, field path, and verbatim excerpt in a claim reference.",
            "Record source support and applicability using qualified reviewer judgment.",
        ],
    }


def metadata_references(metadata: dict[str, Any]) -> list[dict[str, str]]:
    references = []
    for field_path, value in string_values(metadata):
        if field_path.removeprefix("/").split("/", 1)[0] not in EXCLUDED_METADATA_FIELDS:
            references.append({"field_path": field_path, "excerpt": value})
    return references


def string_values(value: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str) and value:
        return [(path, value)]
    if isinstance(value, dict):
        return [item for key, child in value.items() for item in string_values(child, f"{path}/{key}")]
    if isinstance(value, list):
        return [item for index, child in enumerate(value) for item in string_values(child, f"{path}/{index}")]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a BioStonk reviewer packet from local evidence.")
    parser.add_argument("input", type=Path, help="ComparableProgramRequest JSON")
    parser.add_argument("--output", type=Path, required=True, help="Reviewer packet JSON output")
    parser.add_argument("--dataset", type=Path, default=Path("clinical/data/trials.npz"))
    parser.add_argument("--sources", type=Path, default=Path("clinical/data/Emde"))
    parser.add_argument("--metadata", type=Path, default=Path("clinical/data/trial_metadata.json"))
    arguments = parser.parse_args()

    catalog = EvidenceCatalog(arguments.sources)
    metadata_catalog = TrialMetadataCatalog(arguments.metadata) if arguments.metadata.exists() else None
    search = TrialSearch(arguments.dataset, catalog.source_records(), metadata_catalog)
    request = ComparableProgramRequest.model_validate(json.loads(arguments.input.read_text()))
    arguments.output.write_text(json.dumps(build_review_packet(request, search), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()