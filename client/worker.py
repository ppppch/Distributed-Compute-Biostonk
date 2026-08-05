"""Pull-based worker process for the two-computer LAN proof of concept."""

import argparse
from dataclasses import dataclass
import logging
import os
import platform
import socket
import time
from typing import Any

import numpy as np
import requests

from server.inference import DemoAssets, build_demo_assets, prediction_checksum

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerSettings:
    coordinator_url: str
    worker_id: str
    poll_interval: float
    heartbeat_interval: float
    request_timeout: float
    max_request_attempts: int

    @classmethod
    def from_environment(cls, worker_id: str | None = None) -> "WorkerSettings":
        return cls(
            coordinator_url=os.getenv("COORDINATOR_URL", "http://127.0.0.1:8000").rstrip("/"),
            worker_id=worker_id or os.getenv("WORKER_ID", socket.gethostname()),
            poll_interval=float(os.getenv("WORKER_POLL_INTERVAL", "1")),
            heartbeat_interval=float(os.getenv("WORKER_HEARTBEAT_INTERVAL", "5")),
            request_timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
            max_request_attempts=int(os.getenv("WORKER_REQUEST_ATTEMPTS", "3")),
        )


class CoordinatorClient:
    """Small retrying HTTP client used by a worker process."""

    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def register(self, assets: DemoAssets) -> dict[str, Any]:
        return self._request(
            "POST",
            "/workers/register",
            json={
                "worker_id": self.settings.worker_id,
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "available": True,
                "coordinator_url": self.settings.coordinator_url,
                "capabilities": {
                    "model_version": assets.model_version,
                    "baseline_checksum": assets.baseline_checksum,
                    "cpu_count": os.cpu_count(),
                },
            },
        ).json()

    def heartbeat(self) -> dict[str, Any]:
        return self._request("POST", f"/workers/{self.settings.worker_id}/heartbeat").json()

    def claim(self) -> dict[str, Any] | None:
        response = self._request("POST", f"/workers/{self.settings.worker_id}/next-shard")
        return None if response.status_code == 204 else response.json()

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/workers/{self.settings.worker_id}/results",
            json=payload,
        ).json()

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.settings.max_request_attempts + 1):
            try:
                response = self.session.request(
                    method,
                    f"{self.settings.coordinator_url}{path}",
                    timeout=self.settings.request_timeout,
                    **kwargs,
                )
                if response.status_code >= 500 and attempt < self.settings.max_request_attempts:
                    time.sleep(min(0.25 * attempt, 1.0))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as error:
                last_error = error
                if attempt == self.settings.max_request_attempts:
                    raise
                time.sleep(min(0.25 * attempt, 1.0))
        raise RuntimeError("request retry loop ended unexpectedly") from last_error


class WorkerAgent:
    """Register, poll, process one shard at a time, and submit results."""

    def __init__(self, settings: WorkerSettings, assets: DemoAssets | None = None) -> None:
        self.settings = settings
        self.assets = assets or build_demo_assets()
        self.client = CoordinatorClient(settings)
        self._last_heartbeat = 0.0

    def register(self) -> None:
        worker = self.client.register(self.assets)
        LOGGER.info("worker_registered worker_id=%s coordinator=%s", worker["worker_id"], self.settings.coordinator_url)
        self._last_heartbeat = time.monotonic()

    def run_once(self) -> bool:
        self._heartbeat_if_due()
        claim = self.client.claim()
        if claim is None:
            return False
        self._process_claim(claim)
        return True

    def run_forever(self) -> None:
        self.register()
        while True:
            processed = self.run_once()
            if not processed:
                time.sleep(self.settings.poll_interval)

    def _heartbeat_if_due(self) -> None:
        if time.monotonic() - self._last_heartbeat >= self.settings.heartbeat_interval:
            self.client.heartbeat()
            self._last_heartbeat = time.monotonic()

    def _process_claim(self, claim: dict[str, Any]) -> None:
        started_at = time.perf_counter()
        try:
            if claim["model_version"] != self.assets.model_version:
                raise ValueError(
                    f"model version mismatch: worker={self.assets.model_version} coordinator={claim['model_version']}"
                )
            inputs = np.asarray(claim["inputs"], dtype=np.float64)
            predictions = np.asarray(self.assets.model.predict(inputs), dtype=np.int64)
            payload = {
                "job_id": claim["job_id"],
                "shard_id": claim["shard_id"],
                "worker_id": self.settings.worker_id,
                "original_indexes": claim["original_indexes"],
                "predictions": predictions.tolist(),
                "checksum": prediction_checksum(predictions),
                "duration_seconds": time.perf_counter() - started_at,
                "success": True,
                "error": None,
            }
        except Exception as error:
            LOGGER.exception("shard_processing_failed shard_id=%s", claim["shard_id"])
            payload = {
                "job_id": claim["job_id"],
                "shard_id": claim["shard_id"],
                "worker_id": self.settings.worker_id,
                "original_indexes": [],
                "predictions": [],
                "checksum": "",
                "duration_seconds": time.perf_counter() - started_at,
                "success": False,
                "error": str(error),
            }
        response = self.client.submit(payload)
        LOGGER.info(
            "shard_result_submitted job_id=%s shard_id=%s status=%s",
            claim["job_id"],
            claim["shard_id"],
            response["job"]["status"],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a pull-based BioStonk inference worker.")
    parser.add_argument("--worker-id", default=None, help="Override WORKER_ID.")
    parser.add_argument("--once", action="store_true", help="Poll at most once, then exit.")
    arguments = parser.parse_args()
    settings = WorkerSettings.from_environment(arguments.worker_id)
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    agent = WorkerAgent(settings)
    agent.register()
    if arguments.once:
        agent.run_once()
    else:
        while True:
            processed = agent.run_once()
            if not processed:
                time.sleep(settings.poll_interval)


if __name__ == "__main__":
    main()
