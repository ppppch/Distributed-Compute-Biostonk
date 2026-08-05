"""Pydantic API contracts for coordinator, workers, shards, and jobs."""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

JobStatus = Literal[
    "submitted",
    "sharded",
    "distributed",
    "processing",
    "verifying",
    "completed",
    "failed",
]
ShardStatus = Literal["pending", "available", "leased", "completed", "failed"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    jobs: int
    workers: int
    model_version: str


class WorkerRegistrationRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)
    hostname: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=255)
    available: bool = True
    coordinator_url: str = Field(min_length=1)
    capabilities: dict[str, Any] = Field(default_factory=dict)


class WorkerResponse(WorkerRegistrationRequest):
    registered_at: str
    last_heartbeat: str
    status: Literal["available", "unavailable"]


class DemoJobRequest(BaseModel):
    sample_count: int | None = Field(default=None, ge=2, le=540)
    shard_count: int = Field(default=2, ge=2, le=32)


class StatusEvent(BaseModel):
    status: JobStatus
    timestamp: str


class ShardResponse(BaseModel):
    shard_id: str
    status: ShardStatus
    sample_count: int
    index_start: int
    index_end: int
    worker_id: str | None
    processing_duration_seconds: float | None
    checksum: str | None
    attempt_count: int
    lease_expires_at: str | None
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class VerificationResponse(BaseModel):
    exact_match_count: int
    mismatch_count: int
    baseline_checksum: str
    distributed_checksum: str
    baseline_processing_seconds: float
    distributed_processing_seconds: float
    sample_count: int
    verified_at: str


class PredictionJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    state_group: Literal["in_progress", "completed", "failed"]
    lifecycle: list[str]
    created_at: str
    updated_at: str
    completed_at: str | None
    sample_count: int
    shard_count: int
    model_version: str
    baseline_checksum: str
    baseline_processing_seconds: float
    shards: list[ShardResponse]
    verification: VerificationResponse | None
    errors: list[str]
    status_history: list[StatusEvent]


class ShardClaimResponse(BaseModel):
    job_id: str
    shard_id: str
    lease_expires_at: str
    attempt_count: int
    model_version: str
    original_indexes: list[int]
    inputs: list[list[float]]


class ShardResultRequest(BaseModel):
    job_id: str
    shard_id: str
    worker_id: str
    original_indexes: list[int] = Field(default_factory=list)
    predictions: list[int] = Field(default_factory=list)
    checksum: str = ""
    duration_seconds: float = Field(ge=0)
    success: bool
    error: str | None = None

    @model_validator(mode="after")
    def validate_result_shape(self) -> "ShardResultRequest":
        if self.success:
            if not self.original_indexes or not self.predictions or not self.checksum:
                raise ValueError("successful results require indexes, predictions, and checksum")
            if len(self.original_indexes) != len(self.predictions):
                raise ValueError("original_indexes and predictions must have equal lengths")
        elif not self.error:
            raise ValueError("failed results require an error message")
        return self


class ResultAckResponse(BaseModel):
    accepted: bool
    duplicate: bool
    job: PredictionJobResponse


class PredictRequest(BaseModel):
    images: list[list[float]]
    original_index: list[int]


class PredictResponse(BaseModel):
    predictions: list[int]
    original_index: list[int]
    job_id: str | None = None
