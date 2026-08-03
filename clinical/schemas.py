"""Canonical Phase 1 schemas for BioStonk clinical evidence analysis."""

import hashlib
import json

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


class ComparableProgramRequest(BaseModel):
    """A bounded comparable-program search request."""

    profile: ProgramProfile
    anchor_nct_id: str = Field(min_length=1)
    evidence_scope: EvidenceScope = Field(default_factory=EvidenceScope)
    limit: int = Field(default=10, ge=1, le=100)

    def input_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()