"""Thread-safe pull coordinator for deterministic two-worker inference."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
from threading import RLock
import time
from typing import Any
from uuid import uuid4

import numpy as np

from server.inference import DemoAssets, prediction_checksum
from server.schemas import DemoJobRequest, ShardResultRequest, WorkerRegistrationRequest

LOGGER = logging.getLogger(__name__)
LIFECYCLE = ("submitted", "sharded", "distributed", "processing", "verifying", "completed")
TERMINAL_STATUSES = {"completed", "failed"}


class CoordinatorError(Exception):
    """Base class for expected coordinator errors."""


class UnknownResourceError(CoordinatorError):
    """Raised when a job, worker, or shard does not exist."""


class InvalidTransitionError(CoordinatorError):
    """Raised when a job cannot move to its next lifecycle state."""


class ResultConflictError(CoordinatorError):
    """Raised when a result conflicts with the current shard lease or result."""


class ResultValidationError(CoordinatorError):
    """Raised when a result fails coordinator-level integrity checks."""


@dataclass
class WorkerRecord:
    worker_id: str
    hostname: str
    platform: str
    available: bool
    coordinator_url: str
    capabilities: dict[str, Any]
    registered_at: datetime
    last_heartbeat: datetime


@dataclass
class ShardRecord:
    shard_id: str
    indexes: np.ndarray
    inputs: np.ndarray
    created_at: datetime
    updated_at: datetime
    status: str = "pending"
    leased_to: str | None = None
    lease_expires_at: datetime | None = None
    attempt_count: int = 0
    attempted_workers: set[str] = field(default_factory=set)
    processed_by: str | None = None
    processing_duration_seconds: float | None = None
    predictions: np.ndarray | None = None
    checksum: str | None = None
    error: str | None = None
    completed_at: datetime | None = None


@dataclass
class JobRecord:
    job_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    sample_count: int
    shards: list[ShardRecord]
    baseline_predictions: np.ndarray
    baseline_checksum: str
    baseline_processing_seconds: float
    model_version: str
    completed_at: datetime | None = None
    verification: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    status_history: list[dict[str, str]] = field(default_factory=list)


class InMemoryCoordinator:
    """Own workers, jobs, leases, results, and verification in process memory."""

    def __init__(
        self,
        assets: DemoAssets,
        lease_seconds: float = 30.0,
        heartbeat_timeout_seconds: float = 30.0,
        max_shard_attempts: int = 3,
    ) -> None:
        self.assets = assets
        self.lease_seconds = lease_seconds
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.max_shard_attempts = max_shard_attempts
        self._workers: dict[str, WorkerRecord] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._lock = RLock()

    def register_worker(self, request: WorkerRegistrationRequest) -> dict[str, Any]:
        with self._lock:
            now = utc_now()
            existing = self._workers.get(request.worker_id)
            registered_at = existing.registered_at if existing else now
            worker = WorkerRecord(
                **request.model_dump(),
                registered_at=registered_at,
                last_heartbeat=now,
            )
            self._workers[request.worker_id] = worker
            LOGGER.info("worker_registered worker_id=%s hostname=%s", worker.worker_id, worker.hostname)
            return self._worker_dict(worker, now)

    def heartbeat(self, worker_id: str) -> dict[str, Any]:
        with self._lock:
            worker = self._require_worker(worker_id)
            worker.last_heartbeat = utc_now()
            worker.available = True
            return self._worker_dict(worker, worker.last_heartbeat)

    def list_workers(self) -> list[dict[str, Any]]:
        with self._lock:
            now = utc_now()
            return [self._worker_dict(worker, now) for worker in self._workers.values()]

    def submit_job(self, request: DemoJobRequest) -> dict[str, Any]:
        with self._lock:
            sample_count = request.sample_count or len(self.assets.inputs)
            if sample_count > len(self.assets.inputs):
                raise ResultValidationError(
                    f"sample_count cannot exceed the available {len(self.assets.inputs)} inputs"
                )
            if request.shard_count > sample_count:
                raise ResultValidationError("shard_count cannot exceed sample_count")
            now = utc_now()
            job_id = f"job-{uuid4().hex[:12]}"
            baseline_started_at = time.perf_counter()
            baseline_predictions = np.asarray(
                self.assets.model.predict(self.assets.inputs[:sample_count]),
                dtype=np.int64,
            )
            baseline_processing_seconds = time.perf_counter() - baseline_started_at
            index_groups = np.array_split(np.arange(sample_count, dtype=np.int64), request.shard_count)
            shards = [
                ShardRecord(
                    shard_id=f"{job_id}-shard-{position + 1}",
                    indexes=indexes,
                    inputs=self.assets.inputs[indexes],
                    created_at=now,
                    updated_at=now,
                )
                for position, indexes in enumerate(index_groups)
            ]
            job = JobRecord(
                job_id=job_id,
                status="submitted",
                created_at=now,
                updated_at=now,
                sample_count=sample_count,
                shards=shards,
                baseline_predictions=baseline_predictions,
                baseline_checksum=prediction_checksum(baseline_predictions),
                baseline_processing_seconds=baseline_processing_seconds,
                model_version=self.assets.model_version,
                status_history=[{"status": "submitted", "timestamp": iso(now)}],
            )
            self._jobs[job_id] = job
            LOGGER.info("job_submitted job_id=%s samples=%d shards=%d", job_id, sample_count, len(shards))
            return self._job_dict(job)

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            return self._job_dict(self._require_job(job_id))

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                self._job_dict(job)
                for job in sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            ]

    def advance_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._require_job(job_id)
            if job.status in TERMINAL_STATUSES:
                return self._job_dict(job)
            if job.status == "submitted":
                now = utc_now()
                for shard in job.shards:
                    shard.status = "available"
                    shard.updated_at = now
                self._transition(job, "sharded", now)
            elif job.status == "sharded":
                self._transition(job, "distributed")
            elif job.status == "distributed":
                self._transition(job, "processing")
            elif job.status == "processing":
                if any(shard.status == "failed" for shard in job.shards):
                    self._fail_job(job, "One or more shards exhausted their retry limit.")
                elif all(shard.status == "completed" for shard in job.shards):
                    self._transition(job, "verifying")
                else:
                    raise InvalidTransitionError("processing cannot advance until every shard completes")
            elif job.status == "verifying":
                self._verify(job)
            else:
                raise InvalidTransitionError(f"unsupported job status: {job.status}")
            return self._job_dict(job)

    def claim_next_shard(self, worker_id: str) -> dict[str, Any] | None:
        with self._lock:
            worker = self._require_worker(worker_id)
            now = utc_now()
            worker.last_heartbeat = now
            worker.available = True
            self._expire_leases(now)

            for job in sorted(self._jobs.values(), key=lambda item: item.created_at):
                if job.status not in {"distributed", "processing"}:
                    continue
                if any(shard.status == "leased" and shard.leased_to == worker_id for shard in job.shards):
                    continue
                worker_already_used = any(
                    shard.processed_by == worker_id or shard.leased_to == worker_id for shard in job.shards
                )
                for shard in job.shards:
                    if shard.status != "available" or worker_id in shard.attempted_workers:
                        continue
                    if worker_already_used and shard.attempt_count == 0:
                        continue
                    shard.status = "leased"
                    shard.leased_to = worker_id
                    shard.attempt_count += 1
                    shard.attempted_workers.add(worker_id)
                    shard.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                    shard.updated_at = now
                    if job.status == "distributed":
                        self._transition(job, "processing", now)
                    LOGGER.info(
                        "shard_claimed job_id=%s shard_id=%s worker_id=%s attempt=%d",
                        job.job_id,
                        shard.shard_id,
                        worker_id,
                        shard.attempt_count,
                    )
                    return {
                        "job_id": job.job_id,
                        "shard_id": shard.shard_id,
                        "lease_expires_at": iso(shard.lease_expires_at),
                        "attempt_count": shard.attempt_count,
                        "model_version": job.model_version,
                        "original_indexes": shard.indexes.tolist(),
                        "inputs": shard.inputs.tolist(),
                    }
            return None

    def submit_result(self, worker_id: str, result: ShardResultRequest) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            self._require_worker(worker_id)
            if result.worker_id != worker_id:
                raise ResultValidationError("worker ID in path and result body must match")
            job = self._require_job(result.job_id)
            shard = self._require_shard(job, result.shard_id)

            if shard.status == "completed":
                if self._matches_completed_result(shard, result):
                    return True, self._job_dict(job)
                raise ResultConflictError("shard already has a different completed result")
            if shard.status != "leased" or shard.leased_to != worker_id:
                raise ResultConflictError("worker does not hold the active shard lease")

            now = utc_now()
            if not result.success:
                message = result.error or "Worker reported an unknown failure."
                self._release_failed_attempt(job, shard, message, now)
                return False, self._job_dict(job)

            indexes = np.asarray(result.original_indexes, dtype=np.int64)
            predictions = np.asarray(result.predictions, dtype=np.int64)
            if len(np.unique(indexes)) != len(indexes) or set(indexes.tolist()) != set(shard.indexes.tolist()):
                raise ResultValidationError("result indexes must exactly match the leased shard without duplicates")
            calculated_checksum = prediction_checksum(predictions)
            if calculated_checksum != result.checksum:
                message = (
                    f"Checksum mismatch for {shard.shard_id}: "
                    f"reported {result.checksum}, calculated {calculated_checksum}."
                )
                shard.error = message
                shard.status = "failed"
                shard.updated_at = now
                self._fail_job(job, message, now)
                raise ResultValidationError(message)

            order = np.argsort(indexes)
            shard.predictions = predictions[order]
            shard.indexes = indexes[order]
            shard.checksum = calculated_checksum
            shard.processing_duration_seconds = result.duration_seconds
            shard.processed_by = worker_id
            shard.status = "completed"
            shard.completed_at = now
            shard.updated_at = now
            shard.leased_to = None
            shard.lease_expires_at = None
            job.updated_at = now
            LOGGER.info("shard_completed job_id=%s shard_id=%s worker_id=%s", job.job_id, shard.shard_id, worker_id)
            if all(candidate.status == "completed" for candidate in job.shards):
                self._transition(job, "verifying", now)
                self._verify(job)
            return False, self._job_dict(job)

    def _expire_leases(self, now: datetime) -> None:
        for job in self._jobs.values():
            if job.status in TERMINAL_STATUSES:
                continue
            for shard in job.shards:
                if shard.status != "leased" or not shard.lease_expires_at or shard.lease_expires_at > now:
                    continue
                previous_worker = shard.leased_to
                message = f"Lease expired after worker {previous_worker} did not return a result."
                self._release_failed_attempt(job, shard, message, now)
                LOGGER.warning("shard_lease_expired job_id=%s shard_id=%s", job.job_id, shard.shard_id)

    def _release_failed_attempt(
        self,
        job: JobRecord,
        shard: ShardRecord,
        message: str,
        now: datetime,
    ) -> None:
        shard.error = message
        shard.updated_at = now
        shard.leased_to = None
        shard.lease_expires_at = None
        job.errors.append(f"{shard.shard_id}: {message}")
        job.updated_at = now
        if shard.attempt_count >= self.max_shard_attempts:
            shard.status = "failed"
            self._fail_job(job, f"{shard.shard_id} exhausted {self.max_shard_attempts} attempts.", now)
        else:
            shard.status = "available"

    def _verify(self, job: JobRecord) -> None:
        if not all(shard.status == "completed" and shard.predictions is not None for shard in job.shards):
            raise InvalidTransitionError("verification requires every shard result")
        all_indexes = np.concatenate([shard.indexes for shard in job.shards])
        all_predictions = np.concatenate([shard.predictions for shard in job.shards if shard.predictions is not None])
        expected_indexes = np.arange(job.sample_count, dtype=np.int64)
        if len(np.unique(all_indexes)) != job.sample_count or not np.array_equal(np.sort(all_indexes), expected_indexes):
            self._fail_job(job, "Verification found missing or duplicate prediction indexes.")
            return

        order = np.argsort(all_indexes)
        merged = all_predictions[order]
        distributed_checksum = prediction_checksum(merged)
        mismatch_count = int(np.count_nonzero(merged != job.baseline_predictions))
        exact_match_count = job.sample_count - mismatch_count
        now = utc_now()
        job.verification = {
            "exact_match_count": exact_match_count,
            "mismatch_count": mismatch_count,
            "baseline_checksum": job.baseline_checksum,
            "distributed_checksum": distributed_checksum,
            "baseline_processing_seconds": job.baseline_processing_seconds,
            "distributed_processing_seconds": float(
                sum(shard.processing_duration_seconds or 0.0 for shard in job.shards)
            ),
            "sample_count": job.sample_count,
            "verified_at": iso(now),
        }
        if mismatch_count or distributed_checksum != job.baseline_checksum:
            self._fail_job(job, f"Distributed predictions differ from baseline at {mismatch_count} indexes.", now)
            return
        self._transition(job, "completed", now)
        job.completed_at = now
        LOGGER.info("job_completed job_id=%s checksum=%s", job.job_id, distributed_checksum)

    def _transition(self, job: JobRecord, new_status: str, now: datetime | None = None) -> None:
        expected_index = LIFECYCLE.index(job.status) + 1
        if expected_index >= len(LIFECYCLE) or LIFECYCLE[expected_index] != new_status:
            raise InvalidTransitionError(f"invalid transition from {job.status} to {new_status}")
        changed_at = now or utc_now()
        job.status = new_status
        job.updated_at = changed_at
        job.status_history.append({"status": new_status, "timestamp": iso(changed_at)})

    def _fail_job(self, job: JobRecord, message: str, now: datetime | None = None) -> None:
        changed_at = now or utc_now()
        if message not in job.errors:
            job.errors.append(message)
        job.status = "failed"
        job.updated_at = changed_at
        job.completed_at = changed_at
        if not job.status_history or job.status_history[-1]["status"] != "failed":
            job.status_history.append({"status": "failed", "timestamp": iso(changed_at)})
        LOGGER.error("job_failed job_id=%s error=%s", job.job_id, message)

    def _require_worker(self, worker_id: str) -> WorkerRecord:
        try:
            return self._workers[worker_id]
        except KeyError as error:
            raise UnknownResourceError(f"Unknown worker ID: {worker_id}") from error

    def _require_job(self, job_id: str) -> JobRecord:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise UnknownResourceError(f"Unknown job ID: {job_id}") from error

    @staticmethod
    def _require_shard(job: JobRecord, shard_id: str) -> ShardRecord:
        for shard in job.shards:
            if shard.shard_id == shard_id:
                return shard
        raise UnknownResourceError(f"Unknown shard ID: {shard_id}")

    @staticmethod
    def _matches_completed_result(shard: ShardRecord, result: ShardResultRequest) -> bool:
        if not result.success or shard.predictions is None:
            return False
        indexes = np.asarray(result.original_indexes, dtype=np.int64)
        predictions = np.asarray(result.predictions, dtype=np.int64)
        order = np.argsort(indexes)
        return (
            result.worker_id == shard.processed_by
            and result.checksum == shard.checksum
            and np.array_equal(indexes[order], shard.indexes)
            and np.array_equal(predictions[order], shard.predictions)
        )

    def _worker_dict(self, worker: WorkerRecord, now: datetime) -> dict[str, Any]:
        heartbeat_age = (now - worker.last_heartbeat).total_seconds()
        active = worker.available and heartbeat_age <= self.heartbeat_timeout_seconds
        return {
            "worker_id": worker.worker_id,
            "hostname": worker.hostname,
            "platform": worker.platform,
            "available": active,
            "coordinator_url": worker.coordinator_url,
            "capabilities": worker.capabilities,
            "registered_at": iso(worker.registered_at),
            "last_heartbeat": iso(worker.last_heartbeat),
            "status": "available" if active else "unavailable",
        }

    def _job_dict(self, job: JobRecord) -> dict[str, Any]:
        state_group = "completed" if job.status == "completed" else "failed" if job.status == "failed" else "in_progress"
        return {
            "job_id": job.job_id,
            "status": job.status,
            "state_group": state_group,
            "lifecycle": list(LIFECYCLE),
            "created_at": iso(job.created_at),
            "updated_at": iso(job.updated_at),
            "completed_at": iso(job.completed_at) if job.completed_at else None,
            "sample_count": job.sample_count,
            "shard_count": len(job.shards),
            "model_version": job.model_version,
            "baseline_checksum": job.baseline_checksum,
            "baseline_processing_seconds": job.baseline_processing_seconds,
            "shards": [self._shard_dict(shard) for shard in job.shards],
            "verification": job.verification,
            "errors": list(job.errors),
            "status_history": list(job.status_history),
        }

    @staticmethod
    def _shard_dict(shard: ShardRecord) -> dict[str, Any]:
        return {
            "shard_id": shard.shard_id,
            "status": shard.status,
            "sample_count": len(shard.indexes),
            "index_start": int(shard.indexes.min()),
            "index_end": int(shard.indexes.max()),
            "worker_id": shard.processed_by or shard.leased_to,
            "processing_duration_seconds": shard.processing_duration_seconds,
            "checksum": shard.checksum,
            "attempt_count": shard.attempt_count,
            "lease_expires_at": iso(shard.lease_expires_at) if shard.lease_expires_at else None,
            "error": shard.error,
            "created_at": iso(shard.created_at),
            "updated_at": iso(shard.updated_at),
            "completed_at": iso(shard.completed_at) if shard.completed_at else None,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()
