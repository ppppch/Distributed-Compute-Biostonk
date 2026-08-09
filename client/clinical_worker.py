"""Pull-based worker for replicated Trial2Vec comparison tasks."""

import argparse
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import platform
import socket
import time
from typing import Any

import requests

from clinical.demo_jobs import build_candidate_comparison
from clinical.distributed_compute import WORKLOAD_VERSION, canonical_checksum, comparison_artifact_checksum
from clinical.evidence_catalog import EvidenceCatalog
from clinical.metadata_catalog import TrialMetadataCatalog
from clinical.schemas import PredictionCandidate
from clinical.trial_search import TrialSearch

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    coordinator_url: str
    worker_id: str
    dataset_path: Path
    source_directory: Path
    metadata_path: Path
    poll_interval: float = 1.0
    heartbeat_interval: float = 5.0
    request_timeout: float = 15.0

    @classmethod
    def from_environment(cls, worker_id: str | None = None) -> "WorkerSettings":
        return cls(
            coordinator_url=os.getenv("COORDINATOR_URL", "http://127.0.0.1:8001").rstrip("/"),
            worker_id=worker_id or os.getenv("WORKER_ID", socket.gethostname()),
            dataset_path=Path(os.getenv("TRIAL_DATASET_PATH", "clinical/data/trials.npz")),
            source_directory=Path(os.getenv("TRIAL_SOURCE_DIRECTORY", "clinical/data/Emde")),
            metadata_path=Path(os.getenv("TRIAL_METADATA_PATH", "clinical/data/trial_metadata.json")),
            poll_interval=float(os.getenv("WORKER_POLL_INTERVAL", "1")),
            heartbeat_interval=float(os.getenv("WORKER_HEARTBEAT_INTERVAL", "5")),
            request_timeout=float(os.getenv("WORKER_REQUEST_TIMEOUT", "15")),
        )


class CoordinatorClient:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def register(self, artifact_checksum: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/compute/workers/register",
            json={
                "worker_id": self.settings.worker_id,
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "capabilities": {
                    "workload_versions": [WORKLOAD_VERSION],
                    "artifact_checksum": artifact_checksum,
                    "cpu_count": os.cpu_count(),
                    "memory_gb": None,
                },
            },
        ).json()

    def heartbeat(self) -> dict[str, Any]:
        return self._request("POST", f"/compute/workers/{self.settings.worker_id}/heartbeat").json()

    def claim(self) -> dict[str, Any] | None:
        response = self._request("POST", f"/compute/workers/{self.settings.worker_id}/next-task")
        return None if response.status_code == 204 else response.json()

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/compute/workers/{self.settings.worker_id}/results",
            json=payload,
        ).json()

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        response = self.session.request(
            method,
            f"{self.settings.coordinator_url}{path}",
            timeout=self.settings.request_timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response


class ClinicalWorkerAgent:
    def __init__(
        self,
        settings: WorkerSettings,
        search: TrialSearch | None = None,
        client: CoordinatorClient | None = None,
    ) -> None:
        self.settings = settings
        self.artifact_checksum = comparison_artifact_checksum(
            settings.dataset_path,
            settings.source_directory,
            settings.metadata_path,
        )
        self.search = search or build_search(settings)
        self.client = client or CoordinatorClient(settings)
        self._last_heartbeat = 0.0

    def register(self) -> None:
        worker = self.client.register(self.artifact_checksum)
        self._last_heartbeat = time.monotonic()
        LOGGER.info("worker_registered worker_id=%s status=%s", worker["worker_id"], worker["status"])

    def run_once(self) -> bool:
        self._heartbeat_if_due()
        claim = self.client.claim()
        if claim is None:
            return False
        payload = execute_claim(claim, self.settings.worker_id, self.search, self.artifact_checksum)
        acknowledgement = self.client.submit(payload)
        LOGGER.info(
            "comparison_result_submitted job_id=%s task_id=%s status=%s",
            claim["job_id"],
            claim["task_id"],
            acknowledgement["job"]["status"],
        )
        return True

    def run_forever(self) -> None:
        registered = False
        while True:
            try:
                if not registered:
                    self.register()
                    registered = True
                if not self.run_once():
                    time.sleep(self.settings.poll_interval)
            except requests.RequestException as error:
                registered = False
                LOGGER.warning("coordinator_unavailable worker_id=%s error=%s", self.settings.worker_id, error)
                time.sleep(self.settings.poll_interval)

    def _heartbeat_if_due(self) -> None:
        if time.monotonic() - self._last_heartbeat >= self.settings.heartbeat_interval:
            self.client.heartbeat()
            self._last_heartbeat = time.monotonic()


def execute_claim(
    claim: dict[str, Any],
    worker_id: str,
    search: TrialSearch,
    artifact_checksum: str,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        if claim["workload_version"] != WORKLOAD_VERSION:
            raise ValueError(f"Unsupported workload version: {claim['workload_version']}")
        if claim["artifact_checksum"] != artifact_checksum:
            raise ValueError("Task artifact checksum does not match this worker")
        candidate = PredictionCandidate.model_validate(claim["candidate"])
        result = build_candidate_comparison(candidate, search)
        return {
            "job_id": claim["job_id"],
            "task_id": claim["task_id"],
            "worker_id": worker_id,
            "result": result,
            "checksum": canonical_checksum(result),
            "duration_seconds": time.perf_counter() - started_at,
            "success": True,
            "error": None,
        }
    except Exception as error:
        LOGGER.exception("comparison_task_failed task_id=%s", claim.get("task_id"))
        return {
            "job_id": claim.get("job_id", "unknown"),
            "task_id": claim.get("task_id", "unknown"),
            "worker_id": worker_id,
            "result": None,
            "checksum": "",
            "duration_seconds": time.perf_counter() - started_at,
            "success": False,
            "error": str(error),
        }


def build_search(settings: WorkerSettings) -> TrialSearch:
    catalog = EvidenceCatalog(settings.source_directory)
    metadata = TrialMetadataCatalog(settings.metadata_path) if settings.metadata_path.exists() else None
    return TrialSearch(settings.dataset_path, catalog.source_records(), metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an approved BioStonk clinical compute worker.")
    parser.add_argument("--worker-id", default=None, help="Allowlisted worker ID configured on the coordinator.")
    parser.add_argument("--once", action="store_true", help="Register, poll once, and exit.")
    parser.add_argument("--preflight", action="store_true", help="Print local worker and artifact information, then exit.")
    arguments = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = WorkerSettings.from_environment(arguments.worker_id)
    if arguments.preflight:
        print(
            json.dumps(
                {
                    "worker_id": settings.worker_id,
                    "hostname": socket.gethostname(),
                    "coordinator_url": settings.coordinator_url,
                    "workload_version": WORKLOAD_VERSION,
                    "artifact_checksum": comparison_artifact_checksum(
                        settings.dataset_path,
                        settings.source_directory,
                        settings.metadata_path,
                    ),
                    "dataset_path": str(settings.dataset_path),
                    "source_directory": str(settings.source_directory),
                    "metadata_path": str(settings.metadata_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    agent = ClinicalWorkerAgent(settings)
    if arguments.once:
        agent.register()
        agent.run_once()
    else:
        agent.run_forever()


if __name__ == "__main__":
    main()