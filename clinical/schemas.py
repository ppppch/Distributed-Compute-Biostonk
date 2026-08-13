"""Canonical Phase 1 schemas for BioStonk clinical evidence analysis."""

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProgramProfile(BaseModel):
    """The regulatory program context used to scope an analysis run."""

    indication: str = Field(min_length=1)
    disease_subtype: str | None = None
    modality: str | None = None
    proposed_population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    endpoints: list[str] = Field(default_factory=list)
    trial_phase: str | None = None
    jurisdiction: str | None = None


class EvidenceScope(BaseModel):
    """Approved evidence restrictions for one analysis request."""

    source_workbooks: list[str] = Field(default_factory=list)
    sentiment: str | None = None
    condition: str | None = None
    phase: str | None = None
    study_type: str | None = None


class ComparableProgramRequest(BaseModel):
    """A bounded comparable-program search request."""

    profile: ProgramProfile
    anchor_nct_id: str = Field(min_length=1)
    evidence_scope: EvidenceScope = Field(default_factory=EvidenceScope)
    limit: int = Field(default=10, ge=1, le=100)

    def input_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ClaimReference(BaseModel):
    """A verbatim excerpt from one retrieved metadata record."""

    nct_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    content_hash_sha256: str = Field(min_length=1)
    field_path: str = Field(pattern=r"^/")
    excerpt: str = Field(min_length=1)


class ClaimVerificationRequest(BaseModel):
    """A user-supplied claim and the evidence scope used to verify its source."""

    analysis_request: ComparableProgramRequest
    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_type: str = Field(min_length=1)
    reference: ClaimReference


class ReviewableClaim(BaseModel):
    """A claim that must be source-verified before human review."""

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    claim_type: str = Field(min_length=1)
    reference: ClaimReference


class ReviewableBriefRequest(BaseModel):
    analysis_request: ComparableProgramRequest
    claims: list[ReviewableClaim] = Field(min_length=1)


class ClaimReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    note: str | None = None


class ClaimEvaluationReview(BaseModel):
    """A qualified reviewer's assessment for one evaluation example."""

    reviewer_id: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    source_support: Literal["supported", "unsupported", "uncertain"]
    applicability: Literal["applicable", "not_applicable", "uncertain"]


class ClaimEvaluationExample(BaseModel):
    verification_request: ClaimVerificationRequest
    expected_verification_status: Literal["source_verified", "rejected"]
    review: ClaimEvaluationReview


class ProtocolDraft(BaseModel):
    """A local protocol version supplied by a live editing client."""

    protocol_text: str = Field(min_length=1)
    title: str | None = None
    indication: str | None = None
    study_phase: str | None = None
    population: str | None = None
    intervention: str | None = None
    intervention_type: str | None = None
    comparator: str | None = None
    primary_endpoint: str | None = None
    planned_enrollment: int | None = Field(default=None, ge=1)
    planned_site_count: int | None = Field(default=None, ge=1)


class ProtocolDraftAnalysisRequest(BaseModel):
    draft: ProtocolDraft
    previous_draft: ProtocolDraft | None = None


class PredictionCandidate(BaseModel):
    """A protocol candidate paired with a selected Trial2Vec comparison anchor."""

    candidate_id: str = Field(min_length=1)
    anchor_nct_id: str = Field(min_length=1)
    draft: ProtocolDraft


class ClinicalPredictionJobRequest(BaseModel):
    """A bounded local comparison request for one or two protocol candidates."""

    candidates: list[PredictionCandidate] = Field(min_length=1, max_length=2)


class ComputeWorkerRegistrationRequest(BaseModel):
    """Identity and immutable workload capabilities presented by a worker."""

    worker_id: str = Field(min_length=1, max_length=100)
    hostname: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=255)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class ComparisonTaskResultRequest(BaseModel):
    """One worker's deterministic result for a leased comparison replica."""

    job_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    worker_id: str = Field(min_length=1)
    result: dict[str, Any] | None = None
    checksum: str = ""
    duration_seconds: float = Field(ge=0)
    success: bool
    error: str | None = None


class CuratedAnchor(BaseModel):
    """A selectable Trial2Vec anchor trial surfaced in the catalog UI."""

    nct_id: str = Field(min_length=1)
    title: str | None = None
    indication: str | None = None
    phase: str | None = None
    study_type: str | None = None
    overall_status: str | None = None
    source_workbook: str
    metadata_available: bool