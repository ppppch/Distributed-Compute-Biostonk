"""Build deterministic, source-linked Phase 1 evidence briefs."""

from typing import Any

from clinical.schemas import ComparableProgramRequest
from clinical.trial_search import TrialSearch


BRIEF_VERSION = "phase1-local-evidence-brief-v1"


def build_evidence_brief(
    request: ComparableProgramRequest,
    search: TrialSearch,
) -> dict[str, Any]:
    """Compile retrieved evidence without generating clinical or regulatory claims."""
    results = search.find_comparables(
        request.anchor_nct_id,
        limit=request.limit,
        source_workbook=single_source_workbook(request),
        sentiment=request.evidence_scope.sentiment,
        condition=request.evidence_scope.condition,
        phase=request.evidence_scope.phase,
        study_type=request.evidence_scope.study_type,
    )
    evidence = [
        {
            "nct_id": result.nct_id,
            "similarity": result.similarity,
            "sentiment": result.sentiment,
            "source_workbook": result.source_workbook,
            "source": result.source.__dict__,
            "metadata_available": result.metadata is not None,
            "metadata": result.metadata,
        }
        for result in results
    ]
    missing_metadata_nct_ids = [item["nct_id"] for item in evidence if not item["metadata_available"]]
    return {
        "brief_version": BRIEF_VERSION,
        "input_hash_sha256": request.input_hash(),
        "program_profile": request.profile.model_dump(mode="json"),
        "anchor_nct_id": request.anchor_nct_id,
        "evidence_scope": request.evidence_scope.model_dump(mode="json"),
        "retrieval": {
            "method": "local cosine similarity over imported embeddings",
            "requested_limit": request.limit,
            "returned_count": len(evidence),
            "results": evidence,
        },
        "evidence_gaps": {
            "metadata_unavailable_nct_ids": missing_metadata_nct_ids,
            "metadata_coverage": {
                "available_count": len(evidence) - len(missing_metadata_nct_ids),
                "total_count": len(evidence),
            },
        },
        "limitations": [
            "Similarity scores reflect embedding proximity only and do not establish clinical or regulatory comparability.",
            "This brief contains retrieved evidence and provenance, not clinical or regulatory conclusions.",
        ],
    }


def single_source_workbook(request: ComparableProgramRequest) -> str | None:
    workbooks = request.evidence_scope.source_workbooks
    if len(workbooks) > 1:
        raise ValueError("Phase 1 brief generation supports at most one source workbook filter")
    return workbooks[0] if workbooks else None