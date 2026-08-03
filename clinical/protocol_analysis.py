"""Non-predictive protocol draft coverage analysis for the live demo workflow."""

import hashlib
import json
from typing import Any

from clinical.schemas import ProtocolDraft, ProtocolDraftAnalysisRequest


ANALYSIS_VERSION = "phase1-protocol-coverage-v1"
DESIGN_FIELDS = ("indication", "study_phase", "population", "intervention", "comparator", "primary_endpoint")
OPERATIONAL_FIELDS = ("planned_enrollment", "planned_site_count")


def analyze_protocol_draft(request: ProtocolDraftAnalysisRequest) -> dict[str, Any]:
    """Return reproducible coverage signals without predicting trial outcomes."""
    draft = request.draft
    missing_design_fields = missing_fields(draft, DESIGN_FIELDS)
    missing_operational_fields = missing_fields(draft, OPERATIONAL_FIELDS)
    return {
        "analysis_version": ANALYSIS_VERSION,
        "draft_hash_sha256": draft_hash(draft),
        "previous_draft_hash_sha256": draft_hash(request.previous_draft) if request.previous_draft else None,
        "prediction": {
            "available": False,
            "reason": "No validated trial outcome model or calibrated outcome dataset is available.",
        },
        "coverage": {
            "missing_design_fields": missing_design_fields,
            "missing_operational_fields": missing_operational_fields,
            "provided_design_field_count": len(DESIGN_FIELDS) - len(missing_design_fields),
            "required_design_field_count": len(DESIGN_FIELDS),
        },
        "change_signals": change_signals(request.previous_draft, draft),
        "limitations": [
            "Coverage signals identify supplied and missing protocol information only.",
            "This analysis does not predict clinical, operational, or regulatory outcomes.",
        ],
    }


def draft_hash(draft: ProtocolDraft) -> str:
    payload = json.dumps(draft.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def missing_fields(draft: ProtocolDraft, fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if getattr(draft, field) is None]


def change_signals(previous: ProtocolDraft | None, current: ProtocolDraft) -> dict[str, Any]:
    if previous is None:
        return {"has_previous_draft": False, "changed_fields": [], "added_fields": []}
    changed_fields = [
        field
        for field in ProtocolDraft.model_fields
        if getattr(previous, field) != getattr(current, field)
    ]
    added_fields = [
        field
        for field in changed_fields
        if getattr(previous, field) is None and getattr(current, field) is not None
    ]
    return {
        "has_previous_draft": True,
        "changed_fields": changed_fields,
        "added_fields": added_fields,
    }