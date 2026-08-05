"""FastAPI coordinator for deterministic two-computer LAN inference."""

import logging
import os

import numpy as np
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from server.coordinator import (
    CoordinatorError,
    InMemoryCoordinator,
    InvalidTransitionError,
    ResultConflictError,
    ResultValidationError,
    UnknownResourceError,
)
from server.inference import DemoAssets, build_demo_assets
from server.schemas import (
    DemoJobRequest,
    HealthResponse,
    PredictRequest,
    PredictResponse,
    PredictionJobResponse,
    ResultAckResponse,
    ShardClaimResponse,
    ShardResultRequest,
    WorkerRegistrationRequest,
    WorkerResponse,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(
    assets: DemoAssets | None = None,
    lease_seconds: float | None = None,
    heartbeat_timeout_seconds: float | None = None,
    max_shard_attempts: int | None = None,
) -> FastAPI:
    """Create an isolated coordinator app, suitable for production or tests."""

    demo_assets = assets or build_demo_assets()
    coordinator = InMemoryCoordinator(
        demo_assets,
        lease_seconds=lease_seconds or float(os.getenv("SHARD_LEASE_SECONDS", "30")),
        heartbeat_timeout_seconds=heartbeat_timeout_seconds
        or float(os.getenv("WORKER_HEARTBEAT_TIMEOUT_SECONDS", "30")),
        max_shard_attempts=max_shard_attempts or int(os.getenv("MAX_SHARD_ATTEMPTS", "3")),
    )
    application = FastAPI(title="BioStonk Two-Computer Coordinator", version="1.0.0")
    application.state.coordinator = coordinator

    @application.exception_handler(UnknownResourceError)
    async def unknown_resource_handler(_, error: UnknownResourceError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @application.exception_handler(InvalidTransitionError)
    async def invalid_transition_handler(_, error: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(ResultConflictError)
    async def result_conflict_handler(_, error: ResultConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @application.exception_handler(ResultValidationError)
    async def result_validation_handler(_, error: ResultValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @application.exception_handler(CoordinatorError)
    async def coordinator_error_handler(_, error: CoordinatorError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @application.get("/", response_model=dict[str, str])
    def root() -> dict[str, str]:
        return {"status": "Server is running", "role": "coordinator"}

    @application.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            jobs=len(coordinator.list_jobs()),
            workers=len(coordinator.list_workers()),
            model_version=demo_assets.model_version,
        )

    @application.post("/workers/register", response_model=WorkerResponse)
    def register_worker(request: WorkerRegistrationRequest) -> WorkerResponse:
        return WorkerResponse(**coordinator.register_worker(request))

    @application.get("/workers", response_model=list[WorkerResponse])
    def list_workers() -> list[WorkerResponse]:
        return [WorkerResponse(**worker) for worker in coordinator.list_workers()]

    @application.post("/workers/{worker_id}/heartbeat", response_model=WorkerResponse)
    def heartbeat(worker_id: str) -> WorkerResponse:
        return WorkerResponse(**coordinator.heartbeat(worker_id))

    @application.post(
        "/workers/{worker_id}/next-shard",
        response_model=ShardClaimResponse,
        responses={204: {"description": "No shard currently available"}},
    )
    def next_shard(worker_id: str) -> ShardClaimResponse | Response:
        claim = coordinator.claim_next_shard(worker_id)
        if claim is None:
            return Response(status_code=204)
        return ShardClaimResponse(**claim)

    @application.post("/workers/{worker_id}/results", response_model=ResultAckResponse)
    def submit_result(worker_id: str, result: ShardResultRequest) -> ResultAckResponse:
        duplicate, job = coordinator.submit_result(worker_id, result)
        return ResultAckResponse(accepted=True, duplicate=duplicate, job=PredictionJobResponse(**job))

    @application.post("/demo/prediction-jobs", response_model=PredictionJobResponse)
    def submit_job(request: DemoJobRequest) -> PredictionJobResponse:
        return PredictionJobResponse(**coordinator.submit_job(request))

    @application.get("/demo/prediction-jobs", response_model=list[PredictionJobResponse])
    def list_jobs() -> list[PredictionJobResponse]:
        return [PredictionJobResponse(**job) for job in coordinator.list_jobs()]

    @application.get("/demo/prediction-jobs/history", response_model=list[PredictionJobResponse])
    def job_history() -> list[PredictionJobResponse]:
        return list_jobs()

    @application.get("/demo/prediction-jobs/{job_id}", response_model=PredictionJobResponse)
    def get_job(job_id: str) -> PredictionJobResponse:
        return PredictionJobResponse(**coordinator.get_job(job_id))

    @application.post("/demo/prediction-jobs/{job_id}/advance", response_model=PredictionJobResponse)
    def advance_job(job_id: str) -> PredictionJobResponse:
        return PredictionJobResponse(**coordinator.advance_job(job_id))

    @application.post("/predict", response_model=PredictResponse)
    def predict(request: PredictRequest) -> PredictResponse:
        if len(request.images) != len(request.original_index):
            raise ResultValidationError("images and original_index must have equal lengths")
        predictions = np.asarray(demo_assets.model.predict(np.asarray(request.images)), dtype=np.int64)
        return PredictResponse(
            predictions=predictions.tolist(),
            original_index=request.original_index,
            job_id=None,
        )

    return application


app = create_app()