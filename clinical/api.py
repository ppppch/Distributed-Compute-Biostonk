"""Phase 1 API for clinical-trial evidence retrieval."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from clinical.claim_verifier import verify_claim
from clinical.evidence_catalog import EvidenceCatalog
from clinical.evidence_brief import build_evidence_brief
from clinical.demo_jobs import DemoJobCoordinator
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.protocol_analysis import analyze_protocol_draft
from clinical.review_ledger import ReviewLedger
from clinical.schemas import (
    ClaimReviewRequest,
    ClaimVerificationRequest,
    ClinicalPredictionJobRequest,
    ComparableProgramRequest,
    ProtocolDraftAnalysisRequest,
    ReviewableBriefRequest,
)
from clinical.trial_search import TrialSearch


class EvidenceSourceResponse(BaseModel):
    source_id: str
    source_type: str
    source_location: str
    content_hash_sha256: str
    source_modified_at: str


class ComparableTrialResponse(BaseModel):
    nct_id: str
    similarity: float
    sentiment: str
    source_workbook: str
    source: EvidenceSourceResponse
    metadata_available: bool
    metadata: dict | None


class ValidatedAnalysisRequestResponse(BaseModel):
    input_hash_sha256: str
    anchor_nct_id: str
    indication: str


class EvidenceBriefResponse(BaseModel):
    brief_version: str
    input_hash_sha256: str
    program_profile: dict
    anchor_nct_id: str
    evidence_scope: dict
    retrieval: dict
    evidence_gaps: dict
    limitations: list[str]


class ClaimVerificationResponse(BaseModel):
    claim_id: str
    analysis_input_hash_sha256: str
    verification_status: str
    rejection_reasons: list[str]
    reference: dict
    verification_note: str


class ReviewableBriefResponse(BaseModel):
    brief_id: str
    brief_version: str
    analysis_input_hash_sha256: str
    claims: list[dict]
    reviews: list[dict]
    status: str
    created_at: str
    finalized_at: str | None


class ProtocolDraftAnalysisResponse(BaseModel):
    analysis_version: str
    draft_hash_sha256: str
    previous_draft_hash_sha256: str | None
    prediction: dict
    coverage: dict
    change_signals: dict
    limitations: list[str]


class DemoPredictionJobResponse(BaseModel):
    job_id: str
    status: str
    lifecycle: list[str]
    created_at: str
    updated_at: str
    simulation: bool
    execution_notice: str
    tasks: list[dict]
    results: list[dict]


def create_app(
    dataset_path: Path = Path("clinical/data/trials.npz"),
    source_directory: Path = Path("clinical/data/Emde"),
    metadata_path: Path = Path("clinical/data/trial_metadata.json"),
    review_store_path: Path = Path("clinical/data/reviewed_briefs.json"),
) -> FastAPI:
    app = FastAPI(title="BioStonk Clinical Evidence API")
    static_directory = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_directory), name="static")
    catalog = EvidenceCatalog(source_directory)
    metadata_catalog = TrialMetadataCatalog(metadata_path) if metadata_path.exists() else None
    search = TrialSearch(dataset_path, catalog.source_records(), metadata_catalog)
    review_ledger = ReviewLedger(review_store_path)
    demo_jobs = DemoJobCoordinator(search)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def demo_workspace() -> FileResponse:
        return FileResponse(static_directory / "index.html")

    @app.post(
        "/analysis-requests/validate",
        response_model=ValidatedAnalysisRequestResponse,
    )
    def validate_analysis_request(
        request: ComparableProgramRequest,
    ) -> ValidatedAnalysisRequestResponse:
        return ValidatedAnalysisRequestResponse(
            input_hash_sha256=request.input_hash(),
            anchor_nct_id=request.anchor_nct_id,
            indication=request.profile.indication,
        )

    @app.post("/analysis-requests/brief", response_model=EvidenceBriefResponse)
    def create_evidence_brief(request: ComparableProgramRequest) -> EvidenceBriefResponse:
        try:
            return EvidenceBriefResponse(**build_evidence_brief(request, search))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/claims/verify", response_model=ClaimVerificationResponse)
    def verify_claim_reference(request: ClaimVerificationRequest) -> ClaimVerificationResponse:
        try:
            return ClaimVerificationResponse(**verify_claim(request, search))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/protocol-drafts/analyze", response_model=ProtocolDraftAnalysisResponse)
    def analyze_protocol(request: ProtocolDraftAnalysisRequest) -> ProtocolDraftAnalysisResponse:
        return ProtocolDraftAnalysisResponse(**analyze_protocol_draft(request))

    @app.get("/demo/devices")
    def demo_devices() -> list[dict]:
        return demo_jobs.devices()

    @app.get("/demo/prediction-jobs/history", response_model=list[DemoPredictionJobResponse])
    def list_demo_prediction_jobs() -> list[DemoPredictionJobResponse]:
        return [DemoPredictionJobResponse(**job) for job in demo_jobs.list_jobs()]

    @app.post("/demo/prediction-jobs", response_model=DemoPredictionJobResponse)
    def submit_demo_prediction_job(request: ClinicalPredictionJobRequest) -> DemoPredictionJobResponse:
        try:
            return DemoPredictionJobResponse(**demo_jobs.submit(request))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/demo/prediction-jobs/{job_id}", response_model=DemoPredictionJobResponse)
    def get_demo_prediction_job(job_id: str) -> DemoPredictionJobResponse:
        try:
            return DemoPredictionJobResponse(**demo_jobs.get(job_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/demo/prediction-jobs/{job_id}/advance", response_model=DemoPredictionJobResponse)
    def advance_demo_prediction_job(job_id: str) -> DemoPredictionJobResponse:
        try:
            return DemoPredictionJobResponse(**demo_jobs.advance(job_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post("/reviewable-briefs", response_model=ReviewableBriefResponse)
    def create_reviewable_brief(request: ReviewableBriefRequest) -> ReviewableBriefResponse:
        try:
            return ReviewableBriefResponse(**review_ledger.create_brief(request, search))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.post("/reviewable-briefs/{brief_id}/claims/{claim_id}/reviews")
    def review_claim(
        brief_id: str,
        claim_id: str,
        request: ClaimReviewRequest,
    ) -> dict:
        try:
            return review_ledger.review_claim(brief_id, claim_id, request)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.post("/reviewable-briefs/{brief_id}/finalize", response_model=ReviewableBriefResponse)
    def finalize_reviewable_brief(brief_id: str) -> ReviewableBriefResponse:
        try:
            return ReviewableBriefResponse(**review_ledger.finalize_brief(brief_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/reviewable-briefs/{brief_id}/export.md", response_class=PlainTextResponse)
    def export_reviewable_brief(brief_id: str) -> PlainTextResponse:
        try:
            return PlainTextResponse(review_ledger.export_markdown(brief_id), media_type="text/markdown")
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get(
        "/trials/{nct_id}/comparables",
        response_model=list[ComparableTrialResponse],
    )
    def comparable_trials(
        nct_id: str,
        limit: int = Query(default=10, ge=1, le=100),
        source_workbook: str | None = None,
        sentiment: str | None = None,
        condition: str | None = None,
        phase: str | None = None,
        study_type: str | None = None,
    ) -> list[ComparableTrialResponse]:
        try:
            results = search.find_comparables(
                nct_id,
                limit=limit,
                source_workbook=source_workbook,
                sentiment=sentiment,
                condition=condition,
                phase=phase,
                study_type=study_type,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        return [
            ComparableTrialResponse(
                nct_id=result.nct_id,
                similarity=result.similarity,
                sentiment=result.sentiment,
                source_workbook=result.source_workbook,
                source=EvidenceSourceResponse(**result.source.__dict__),
                metadata_available=result.metadata is not None,
                metadata=result.metadata,
            )
            for result in results
        ]

    return app


app = create_app()