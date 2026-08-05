"""Command-line client for submitting and inspecting coordinator demo jobs."""

import argparse
import json
import os
from typing import Any

import requests


def request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    coordinator_url = os.getenv("COORDINATOR_URL", "http://127.0.0.1:8000").rstrip("/")
    timeout = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    response = requests.request(method, f"{coordinator_url}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def submit(sample_count: int | None, shard_count: int) -> dict[str, Any]:
    """Submit a job and advance it until workers may claim shards."""

    job = request(
        "POST",
        "/demo/prediction-jobs",
        {"sample_count": sample_count, "shard_count": shard_count},
    )
    job = request("POST", f"/demo/prediction-jobs/{job['job_id']}/advance")
    return request("POST", f"/demo/prediction-jobs/{job['job_id']}/advance")


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit or inspect BioStonk LAN demo jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--sample-count", type=int, default=None)
    submit_parser.add_argument("--shard-count", type=int, default=2)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("job_id", nargs="?", default=os.getenv("JOB_ID"))
    subparsers.add_parser("workers")
    arguments = parser.parse_args()

    if arguments.command == "submit":
        result = submit(arguments.sample_count, arguments.shard_count)
    elif arguments.command == "status":
        path = f"/demo/prediction-jobs/{arguments.job_id}" if arguments.job_id else "/demo/prediction-jobs"
        result = request("GET", path)
    else:
        result = request("GET", "/workers")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
