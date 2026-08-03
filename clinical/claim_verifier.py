"""Verify that claim references exactly match retrieved metadata evidence."""

from typing import Any

from clinical.evidence_brief import build_evidence_brief
from clinical.schemas import ClaimReference, ClaimVerificationRequest
from clinical.trial_search import TrialSearch


def verify_claim(
    request: ClaimVerificationRequest,
    search: TrialSearch,
) -> dict[str, Any]:
    """Verify a reference's source identity, hash, field path, and excerpt."""
    evidence = build_evidence_brief(request.analysis_request, search)["retrieval"]["results"]
    trial = next((item for item in evidence if item["nct_id"] == request.reference.nct_id), None)
    if trial is None:
        return rejected(request, "referenced_trial_not_retrieved")
    metadata = trial["metadata"]
    if metadata is None:
        return rejected(request, "referenced_trial_has_no_metadata")
    if request.reference.source_id != metadata.get("source_id"):
        return rejected(request, "source_id_mismatch")
    if request.reference.content_hash_sha256 != metadata.get("content_hash_sha256"):
        return rejected(request, "content_hash_mismatch")

    field_value = value_at_pointer(metadata, request.reference)
    if field_value is None:
        return rejected(request, "field_path_not_found")
    if request.reference.excerpt not in field_value:
        return rejected(request, "excerpt_not_found_in_source_field")

    return {
        "claim_id": request.claim_id,
        "analysis_input_hash_sha256": request.analysis_request.input_hash(),
        "verification_status": "source_verified",
        "rejection_reasons": [],
        "reference": request.reference.model_dump(mode="json"),
        "verification_note": "Source verification confirms a verbatim excerpt only; it does not establish the claim's clinical or regulatory validity.",
    }


def value_at_pointer(metadata: dict[str, Any], reference: ClaimReference) -> str | None:
    value: Any = metadata
    for segment in reference.field_path.removeprefix("/").split("/"):
        if isinstance(value, dict):
            value = value.get(segment)
        elif isinstance(value, list) and segment.isdigit() and int(segment) < len(value):
            value = value[int(segment)]
        else:
            return None
    return value if isinstance(value, str) else None


def rejected(request: ClaimVerificationRequest, reason: str) -> dict[str, Any]:
    return {
        "claim_id": request.claim_id,
        "analysis_input_hash_sha256": request.analysis_request.input_hash(),
        "verification_status": "rejected",
        "rejection_reasons": [reason],
        "reference": request.reference.model_dump(mode="json"),
        "verification_note": "Source verification was not completed.",
    }