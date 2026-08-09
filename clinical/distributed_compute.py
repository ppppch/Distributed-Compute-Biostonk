"""Pull-based coordination for verified clinical comparison workloads."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from clinical.schemas import (
    ClinicalPredictionJobRequest,
    ComparisonTaskResultRequest,
    ComputeWorkerRegistrationRequest,
)

WORKLOAD_VERSION = "trial2vec-comparison-v1"
LIFECYCLE = ("queued", "running", "verifying", "aggregated", "completed")
TERMINAL_STATUSES = {"completed", "failed"}


class ComputeCoordinatorError(Exception):
    """Base class for expected compute coordination failures."""


class UnknownComputeResourceError(ComputeCoordinatorError):
    """Raised when a worker, job, or task does not exist."""


class WorkerApprovalError(ComputeCoordinatorError):
    """Raised when worker identity or artifacts do not satisfy policy."""


class TaskConflictError(ComputeCoordinatorError):
    """Raised when a worker does not hold the active task lease."""


class TaskValidationError(ComputeCoordinatorError):
    """Raised when a worker result fails integrity validation."""


@dataclass
class WorkerRecord:
    worker_id: str
    hostname: str
    platform: str
    capabilities: dict[str, Any]
    registered_at: datetime
    last_heartbeat: datetime


@dataclass
class TaskRecord:
    task_id: str
    candidate_id: str
    replica: int
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    status: str = "queued"
    leased_to: str | None = None
    lease_expires_at: datetime | None = None
    attempt_count: int = 0
    attempted_workers: set[str] = field(default_factory=set)
    processed_by: str | None = None
    duration_seconds: float | None = None
    result: dict[str, Any] | None = None
    checksum: str | None = None
    error: str | None = None
    completed_at: datetime | None = None


@dataclass
class JobRecord:
    job_id: str
    status: str
    candidate_order: list[str]
    tasks: list[TaskRecord]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    verification: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    status_history: list[dict[str, str]] = field(default_factory=list)


class ClinicalComputeCoordinator:
    """Coordinate replicated tasks across explicitly allowlisted worker IDs."""

    def __init__(
        self,
        artifact_checksum: str,
        approved_worker_ids: set[str],
        replicas: int = 2,
        lease_seconds: float = 30.0,
        heartbeat_timeout_seconds: float = 30.0,
        max_task_attempts: int = 3,
        require_distinct_hosts: bool = False,
    ) -> None:
        if replicas < 2:
            raise ValueError("at least two replicas are required for independent verification")
        self.artifact_checksum = artifact_checksum
        self.approved_worker_ids = set(approved_worker_ids)
        self.replicas = replicas
        self.lease_seconds = lease_seconds
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.max_task_attempts = max_task_attempts
        self.require_distinct_hosts = require_distinct_hosts
        self._workers: dict[str, WorkerRecord] = {}
        self._jobs: dict[str, JobRecord] = {}
        self._lock = RLock()

    def register_worker(self, request: ComputeWorkerRegistrationRequest) -> dict[str, Any]:
        with self._lock:
            if request.worker_id not in self.approved_worker_ids:
                raise WorkerApprovalError(f"Worker ID is not approved: {request.worker_id}")
            versions = request.capabilities.get("workload_versions", [])
            if WORKLOAD_VERSION not in versions:
                raise WorkerApprovalError(f"Worker does not support {WORKLOAD_VERSION}")
            if request.capabilities.get("artifact_checksum") != self.artifact_checksum:
                raise WorkerApprovalError("Worker artifact checksum does not match the coordinator")
            now = utc_now()
            existing = self._workers.get(request.worker_id)
            record = WorkerRecord(
                worker_id=request.worker_id,
                hostname=request.hostname,
                platform=request.platform,
                capabilities=request.capabilities,
                registered_at=existing.registered_at if existing else now,
                last_heartbeat=now,
            )
            self._workers[record.worker_id] = record
            return self._worker_dict(record, now)

    def heartbeat(self, worker_id: str) -> dict[str, Any]:
        with self._lock:
            worker = self._require_worker(worker_id)
            worker.last_heartbeat = utc_now()
            return self._worker_dict(worker, worker.last_heartbeat)

    def list_workers(self) -> list[dict[str, Any]]:
        with self._lock:
            now = utc_now()
            return [self._worker_dict(worker, now) for worker in self._workers.values()]

    def readiness(self) -> dict[str, Any]:
        with self._lock:
            now = utc_now()
            active_workers = [worker for worker in self._workers.values() if self._is_worker_active(worker, now)]
            distinct_hosts = {worker.hostname for worker in active_workers}
            blockers = []
            if len(active_workers) < self.replicas:
                blockers.append(f"At least {self.replicas} active workers are required.")
            if self.require_distinct_hosts and len(distinct_hosts) < self.replicas:
                blockers.append(f"At least {self.replicas} distinct active hostnames are required.")
            return {
                "ready": not blockers,
                "mode": "two-host-lan-pilot" if self.require_distinct_hosts else "single-host-development",
                "production_ready": False,
                "required_replicas": self.replicas,
                "registered_worker_count": len(self._workers),
                "active_worker_count": len(active_workers),
                "distinct_active_host_count": len(distinct_hosts),
                "active_hostnames": sorted(distinct_hosts),
                "artifact_checksum": self.artifact_checksum,
                "workload_version": WORKLOAD_VERSION,
                "blockers": blockers,
                "remaining_production_controls": [
                    "Mutual TLS and certificate-backed device identity",
                    "Persistent job and audit storage",
                    "Encrypted task payloads and sandboxed execution",
                    "Hardware attestation and tenant isolation",
                ],
            }

    def submit_job(self, request: ClinicalPredictionJobRequest) -> dict[str, Any]:
        with self._lock:
            now = utc_now()
            job_id = f"compute-{uuid4().hex[:12]}"
            tasks = [
                TaskRecord(
                    task_id=f"{job_id}-{candidate.candidate_id}-replica-{replica}",
                    candidate_id=candidate.candidate_id,
                    replica=replica,
                    payload=candidate.model_dump(mode="json"),
                    created_at=now,
                    updated_at=now,
                )
                for candidate in request.candidates
                for replica in range(1, self.replicas + 1)
            ]
            job = JobRecord(
                job_id=job_id,
                status="queued",
                candidate_order=[candidate.candidate_id for candidate in request.candidates],
                tasks=tasks,
                created_at=now,
                updated_at=now,
                status_history=[{"status": "queued", "timestamp": iso(now)}],
            )
            self._jobs[job_id] = job
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

    def claim_next_task(self, worker_id: str) -> dict[str, Any] | None:
        with self._lock:
            worker = self._require_worker(worker_id)
            now = utc_now()
            worker.last_heartbeat = now
            self._expire_leases(now)
            for job in sorted(self._jobs.values(), key=lambda item: item.created_at):
                if job.status in TERMINAL_STATUSES:
                    continue
                for task in job.tasks:
                    same_candidate_workers = {
                        candidate.processed_by or candidate.leased_to
                        for candidate in job.tasks
                        if candidate.candidate_id == task.candidate_id
                    }
                    same_candidate_hosts = {
                        self._workers[worker_id].hostname
                        for worker_id in same_candidate_workers
                        if worker_id in self._workers
                    }
                    if (
                        task.status != "queued"
                        or worker_id in task.attempted_workers
                        or worker_id in same_candidate_workers
                        or (self.require_distinct_hosts and worker.hostname in same_candidate_hosts)
                    ):
                        continue
                    task.status = "leased"
                    task.leased_to = worker_id
                    task.attempt_count += 1
                    task.attempted_workers.add(worker_id)
                    task.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
                    task.updated_at = now
                    if job.status == "queued":
                        self._transition(job, "running", now)
                    return {
                        "job_id": job.job_id,
                        "task_id": task.task_id,
                        "candidate_id": task.candidate_id,
                        "replica": task.replica,
                        "workload_version": WORKLOAD_VERSION,
                        "artifact_checksum": self.artifact_checksum,
                        "lease_expires_at": iso(task.lease_expires_at),
                        "attempt_count": task.attempt_count,
                        "candidate": task.payload,
                    }
            return None

    def submit_result(
        self,
        worker_id: str,
        request: ComparisonTaskResultRequest,
    ) -> tuple[bool, dict[str, Any]]:
        with self._lock:
            self._require_worker(worker_id)
            if request.worker_id != worker_id:
                raise TaskValidationError("Worker ID in path and result body must match")
            job = self._require_job(request.job_id)
            task = self._require_task(job, request.task_id)
            if task.status == "completed":
                if self._matches_completed_result(task, request):
                    return True, self._job_dict(job)
                raise TaskConflictError("Task already has a different completed result")
            if task.status != "leased" or task.leased_to != worker_id:
                raise TaskConflictError("Worker does not hold the active task lease")
            now = utc_now()
            if not request.success:
                self._release_failed_attempt(job, task, request.error or "Worker failure", now)
                return False, self._job_dict(job)
            if request.result is None:
                raise TaskValidationError("Successful task results require a result payload")
            calculated_checksum = canonical_checksum(request.result)
            if calculated_checksum != request.checksum:
                self._fail_job(job, f"Task checksum mismatch for {task.task_id}", now)
                raise TaskValidationError("Reported checksum does not match the result payload")
            if request.result.get("candidate_id") != task.candidate_id:
                raise TaskValidationError("Result candidate ID does not match the leased task")
            task.status = "completed"
            task.processed_by = worker_id
            task.duration_seconds = request.duration_seconds
            task.result = request.result
            task.checksum = calculated_checksum
            task.completed_at = now
            task.updated_at = now
            task.leased_to = None
            task.lease_expires_at = None
            job.updated_at = now
            if all(candidate.status == "completed" for candidate in job.tasks):
                self._verify_and_aggregate(job, now)
            return False, self._job_dict(job)

    def devices(self) -> list[dict[str, Any]]:
        """List approved endpoints with live connectivity.

        Registered workers are reported with heartbeat recency, capacity, and
        assigned tasks. Approved IDs that have not connected this server
        session appear as "not connected" so the dashboard shows expected
        endpoints alongside live devices.
        """
        with self._lock:
            now = utc_now()
            devices = []
            for approved_id in sorted(self.approved_worker_ids):
                worker = self._workers.get(approved_id)
                if worker is None:
                    devices.append(
                        {
                            "device_id": approved_id,
                            "name": approved_id,
                            "type": "Approved endpoint",
                            "cpu_cores": None,
                            "memory_gb": None,
                            "availability": "not connected",
                            "allowlisted": True,
                            "connected": False,
                            "assigned_tasks": [],
                            "last_heartbeat": None,
                        }
                    )
                    continue
                active_tasks = [
                    self._task_dict(task)
                    for job in self._jobs.values()
                    for task in job.tasks
                    if task.leased_to == worker.worker_id
                ]
                active = self._is_worker_active(worker, now)
                devices.append(
                    {
                        "device_id": worker.worker_id,
                        "name": worker.hostname,
                        "type": worker.platform,
                        "cpu_cores": worker.capabilities.get("cpu_count"),
                        "memory_gb": worker.capabilities.get("memory_gb"),
                        "availability": "available" if active else "unavailable",
                        "allowlisted": True,
                        "connected": True,
                        "assigned_tasks": active_tasks,
                        "last_heartbeat": iso(worker.last_heartbeat),
                    }
                )
            return devices

    def _verify_and_aggregate(self, job: JobRecord, now: datetime) -> None:
        self._transition(job, "verifying", now)
        results = []
        candidate_checksums: dict[str, str] = {}
        for candidate_id in job.candidate_order:
            replicas = [task for task in job.tasks if task.candidate_id == candidate_id]
            checksums = {task.checksum for task in replicas}
            workers = {task.processed_by for task in replicas}
            hostnames = {
                self._workers[worker_id].hostname
                for worker_id in workers
                if worker_id in self._workers
            }
            if (
                len(replicas) != self.replicas
                or len(checksums) != 1
                or len(workers) != self.replicas
                or (self.require_distinct_hosts and len(hostnames) != self.replicas)
            ):
                self._fail_job(job, f"Replica verification failed for {candidate_id}", now)
                return
            result = replicas[0].result
            if result is None:
                self._fail_job(job, f"Replica result missing for {candidate_id}", now)
                return
            results.append(result)
            candidate_checksums[candidate_id] = next(iter(checksums)) or ""
        self._transition(job, "aggregated", now)
        aggregate_checksum = canonical_checksum(results)
        job.results = results
        job.verification = {
            "method": "independent_replica_agreement",
            "workload_version": WORKLOAD_VERSION,
            "artifact_checksum": self.artifact_checksum,
            "replica_count": self.replicas,
            "verified_task_count": len(job.tasks),
            "worker_ids": sorted(task.processed_by for task in job.tasks if task.processed_by),
            "worker_hostnames": sorted(
                {self._workers[task.processed_by].hostname for task in job.tasks if task.processed_by}
            ),
            "distinct_host_count": len(
                {self._workers[task.processed_by].hostname for task in job.tasks if task.processed_by}
            ),
            "distinct_hosts_required": self.require_distinct_hosts,
            "candidate_checksums": candidate_checksums,
            "aggregate_checksum": aggregate_checksum,
            "verified_at": iso(now),
        }
        self._transition(job, "completed", now)
        job.completed_at = now

    def _expire_leases(self, now: datetime) -> None:
        for job in self._jobs.values():
            if job.status in TERMINAL_STATUSES:
                continue
            for task in job.tasks:
                if task.status != "leased" or not task.lease_expires_at or task.lease_expires_at > now:
                    continue
                self._release_failed_attempt(job, task, "Task lease expired", now)

    def _release_failed_attempt(self, job: JobRecord, task: TaskRecord, message: str, now: datetime) -> None:
        task.error = message
        task.leased_to = None
        task.lease_expires_at = None
        task.updated_at = now
        job.errors.append(f"{task.task_id}: {message}")
        job.updated_at = now
        if task.attempt_count >= self.max_task_attempts:
            task.status = "failed"
            self._fail_job(job, f"{task.task_id} exhausted its retry limit", now)
        else:
            task.status = "queued"

    def _transition(self, job: JobRecord, status: str, now: datetime) -> None:
        job.status = status
        job.updated_at = now
        job.status_history.append({"status": status, "timestamp": iso(now)})

    def _fail_job(self, job: JobRecord, message: str, now: datetime) -> None:
        if message not in job.errors:
            job.errors.append(message)
        job.status = "failed"
        job.updated_at = now
        job.completed_at = now
        job.status_history.append({"status": "failed", "timestamp": iso(now)})

    def _require_worker(self, worker_id: str) -> WorkerRecord:
        try:
            return self._workers[worker_id]
        except KeyError as error:
            raise UnknownComputeResourceError(f"Unknown worker ID: {worker_id}") from error

    def _require_job(self, job_id: str) -> JobRecord:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise UnknownComputeResourceError(f"Unknown job ID: {job_id}") from error

    @staticmethod
    def _require_task(job: JobRecord, task_id: str) -> TaskRecord:
        for task in job.tasks:
            if task.task_id == task_id:
                return task
        raise UnknownComputeResourceError(f"Unknown task ID: {task_id}")

    @staticmethod
    def _matches_completed_result(task: TaskRecord, request: ComparisonTaskResultRequest) -> bool:
        return (
            request.success
            and request.worker_id == task.processed_by
            and request.checksum == task.checksum
            and request.result == task.result
        )

    def _is_worker_active(self, worker: WorkerRecord, now: datetime) -> bool:
        return (now - worker.last_heartbeat).total_seconds() <= self.heartbeat_timeout_seconds

    def _worker_dict(self, worker: WorkerRecord, now: datetime) -> dict[str, Any]:
        active = self._is_worker_active(worker, now)
        return {
            "worker_id": worker.worker_id,
            "hostname": worker.hostname,
            "platform": worker.platform,
            "capabilities": worker.capabilities,
            "allowlisted": True,
            "registered_at": iso(worker.registered_at),
            "last_heartbeat": iso(worker.last_heartbeat),
            "status": "available" if active else "unavailable",
        }

    def _job_dict(self, job: JobRecord) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "lifecycle": list(LIFECYCLE),
            "created_at": iso(job.created_at),
            "updated_at": iso(job.updated_at),
            "completed_at": iso(job.completed_at) if job.completed_at else None,
            "simulation": False,
            "execution_notice": "Allowlisted worker processes executed replicated Trial2Vec comparison tasks; results require checksum agreement before aggregation.",
            "tasks": [self._task_dict(task) for task in job.tasks],
            "results": job.results,
            "verification": job.verification,
            "errors": list(job.errors),
            "status_history": list(job.status_history),
        }

    @staticmethod
    def _task_dict(task: TaskRecord) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "candidate_id": task.candidate_id,
            "replica": task.replica,
            "status": task.status,
            "worker_id": task.processed_by or task.leased_to,
            "attempt_count": task.attempt_count,
            "duration_seconds": task.duration_seconds,
            "checksum": task.checksum,
            "error": task.error,
        }


def canonical_checksum(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def comparison_artifact_checksum(
    dataset_path: Path,
    source_directory: Path,
    metadata_path: Path,
) -> str:
    """Fingerprint every local artifact that can affect comparison execution."""
    digest = hashlib.sha256()
    paths = [("dataset", dataset_path)]
    paths.extend((f"source/{path.name}", path) for path in sorted(source_directory.glob("*.xlsx")))
    if metadata_path.exists():
        paths.append(("metadata", metadata_path))
    for role, path in paths:
        digest.update(role.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat()