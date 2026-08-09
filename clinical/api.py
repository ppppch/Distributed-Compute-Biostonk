"""Phase 1 API for clinical-trial evidence retrieval."""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from clinical.claim_verifier import verify_claim
from clinical.evidence_catalog import EvidenceCatalog
from clinical.evidence_brief import build_evidence_brief
from clinical.distributed_compute import (
    ClinicalComputeCoordinator,
    ComputeCoordinatorError,
    TaskConflictError,
    TaskValidationError,
    UnknownComputeResourceError,
    WorkerApprovalError,
    comparison_artifact_checksum,
)
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.protocol_analysis import analyze_protocol_draft
from clinical.review_ledger import ReviewLedger
from clinical.schemas import (
    ClaimReviewRequest,
    ClaimVerificationRequest,
    ClinicalPredictionJobRequest,
    ComparisonTaskResultRequest,
    ComparableProgramRequest,
    ComputeWorkerRegistrationRequest,
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


class ComparisonJobResponse(BaseModel):
    job_id: str
    status: str
    lifecycle: list[str]
    created_at: str
    updated_at: str
    simulation: bool
    execution_notice: str
    tasks: list[dict]
    results: list[dict]
    completed_at: str | None
    verification: dict | None
    errors: list[str]
    status_history: list[dict]


def create_app(
    dataset_path: Path = Path("clinical/data/trials.npz"),
    source_directory: Path = Path("clinical/data/Emde"),
    metadata_path: Path = Path("clinical/data/trial_metadata.json"),
    review_store_path: Path = Path("clinical/data/reviewed_briefs.json"),
    approved_worker_ids: set[str] | None = None,
    require_distinct_hosts: bool | None = None,
) -> FastAPI:
    app = FastAPI(title="BioStonk Clinical Evidence API")
    static_directory = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_directory), name="static")
    catalog = EvidenceCatalog(source_directory)
    metadata_catalog = TrialMetadataCatalog(metadata_path) if metadata_path.exists() else None
    search = TrialSearch(dataset_path, catalog.source_records(), metadata_catalog)
    review_ledger = ReviewLedger(review_store_path)
    configured_worker_ids = approved_worker_ids or {
        worker_id.strip()
        for worker_id in os.getenv(
            "BIOSTONK_APPROVED_WORKERS",
            "local-worker-a,local-worker-b",
        ).split(",")
        if worker_id.strip()
    }
    compute = ClinicalComputeCoordinator(
        artifact_checksum=comparison_artifact_checksum(dataset_path, source_directory, metadata_path),
        approved_worker_ids=configured_worker_ids,
        require_distinct_hosts=(
            require_distinct_hosts
            if require_distinct_hosts is not None
            else os.getenv("BIOSTONK_REQUIRE_DISTINCT_HOSTS", "false").casefold() in {"1", "true", "yes"}
        ),
    )
    app.state.compute_coordinator = compute
    app.state.trial_search = search

    @app.exception_handler(UnknownComputeResourceError)
    async def unknown_compute_resource(_, error: UnknownComputeResourceError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(WorkerApprovalError)
    async def worker_approval_failure(_, error: WorkerApprovalError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @app.exception_handler(TaskConflictError)
    async def task_conflict(_, error: TaskConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(TaskValidationError)
    async def task_validation_failure(_, error: TaskValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(ComputeCoordinatorError)
    async def compute_failure(_, error: ComputeCoordinatorError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

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

    @app.post("/compute/workers/register")
    def register_compute_worker(request: ComputeWorkerRegistrationRequest) -> dict:
        return compute.register_worker(request)

    @app.get("/compute/workers")
    def list_compute_workers() -> list[dict]:
        return compute.list_workers()

    @app.get("/compute/readiness")
    def compute_readiness() -> dict:
        return compute.readiness()

    @app.post("/compute/workers/{worker_id}/heartbeat")
    def heartbeat_compute_worker(worker_id: str) -> dict:
        return compute.heartbeat(worker_id)

    @app.post(
        "/compute/workers/{worker_id}/next-task",
        response_model=None,
        responses={204: {"description": "No comparison task is currently available"}},
    )
    def claim_compute_task(worker_id: str) -> dict | Response:
        task = compute.claim_next_task(worker_id)
        return Response(status_code=204) if task is None else task

    @app.post("/compute/workers/{worker_id}/results")
    def submit_compute_result(worker_id: str, request: ComparisonTaskResultRequest) -> dict:
        duplicate, job = compute.submit_result(worker_id, request)
        return {"accepted": True, "duplicate": duplicate, "job": job}

    @app.get("/demo/devices")
    def demo_devices() -> list[dict]:
        return compute.devices()

    @app.get("/comparison-jobs/history", response_model=list[ComparisonJobResponse])
    @app.get("/demo/prediction-jobs/history", response_model=list[ComparisonJobResponse], include_in_schema=False)
    def list_comparison_jobs() -> list[ComparisonJobResponse]:
        return [ComparisonJobResponse(**job) for job in compute.list_jobs()]

    @app.post("/comparison-jobs", response_model=ComparisonJobResponse)
    @app.post("/demo/prediction-jobs", response_model=ComparisonJobResponse, include_in_schema=False)
    def submit_comparison_job(request: ClinicalPredictionJobRequest) -> ComparisonJobResponse:
        readiness = compute.readiness()
        if not readiness["ready"]:
            raise HTTPException(status_code=409, detail=" ".join(readiness["blockers"]))
        return ComparisonJobResponse(**compute.submit_job(request))

    @app.get("/comparison-jobs/{job_id}", response_model=ComparisonJobResponse)
    @app.get("/demo/prediction-jobs/{job_id}", response_model=ComparisonJobResponse, include_in_schema=False)
    def get_comparison_job(job_id: str) -> ComparisonJobResponse:
        return ComparisonJobResponse(**compute.get_job(job_id))

    @app.post("/comparison-jobs/{job_id}/advance", response_model=ComparisonJobResponse, include_in_schema=False)
    @app.post("/demo/prediction-jobs/{job_id}/advance", response_model=ComparisonJobResponse, include_in_schema=False)
    def legacy_poll_comparison_job(job_id: str) -> ComparisonJobResponse:
        return get_comparison_job(job_id)

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