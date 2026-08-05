# BioStonk Two-Computer Distributed Inference

BioStonk is a centralized proof of concept for deterministic machine-learning
inference across two laptops on the same local network. A FastAPI coordinator
owns jobs and shards. Identical pull workers claim separate shards, run the same
fixed scikit-learn digits model, and return predictions for ordered verification.

This iteration is **not** a decentralized mesh. It does not provide peer-to-peer
routing, NAT traversal, browser inference, blockchain coordination, cloud
orchestration, or production security.

## Architecture

```text
Client
  |
  | POST /demo/prediction-jobs
  v
FastAPI coordinator on Computer A
  |-- computes the single-machine baseline
  |-- creates two deterministic shards
  |-- leases shard 1 <---- worker-a polls and claims
  |-- leases shard 2 <---- worker-b polls and claims over the LAN
  |-- validates indexes, checksums, leases, and worker IDs
  |-- merges predictions in original input order
  |-- compares merged predictions with the baseline
  `-- marks the job completed or failed
```

Workers only make outbound requests to the coordinator. Computer A never needs
to initiate an inbound connection to Computer B.

## Main Components

| Path | Purpose |
|---|---|
| `server/server.py` | FastAPI app and coordinator routes |
| `server/coordinator.py` | Thread-safe jobs, workers, leases, retries, merge, and verification |
| `server/inference.py` | Fixed digits split, RandomForest model, baseline, and checksums |
| `server/schemas.py` | Pydantic API contracts |
| `client/worker.py` | Pull worker with heartbeat, timeout, and bounded request retries |
| `client/demo_client.py` | Submit and inspect demo jobs |
| `tests/test_job_lifecycle.py` | Two-worker coordinator acceptance tests |
| `clinical/` | Separate clinical product-demo workspace and API |

The older file-based pipeline remains available through the `legacy-*` Make
targets for comparison. It is not the active LAN architecture.

## Installation

Use the same repository commit and Python dependencies on both computers.

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

The coordinator and each worker deterministically train the same lightweight
RandomForest at startup. No model download or LLM is required. Generated model,
dataset, cache, and virtual-environment files are ignored by Git.

## Configuration

| Variable | Default | Used by |
|---|---:|---|
| `COORDINATOR_HOST` | `0.0.0.0` | Coordinator bind host |
| `COORDINATOR_PORT` | `8000` | Coordinator port |
| `COORDINATOR_URL` | `http://127.0.0.1:8000` | Workers and demo client |
| `WORKER_ID` | Local hostname | Worker identity |
| `WORKER_POLL_INTERVAL` | `1` second | Worker polling |
| `WORKER_HEARTBEAT_INTERVAL` | `5` seconds | Worker heartbeat |
| `SHARD_LEASE_SECONDS` | `30` seconds | Coordinator lease duration |
| `REQUEST_TIMEOUT_SECONDS` | `10` seconds | Worker/client HTTP timeout |
| `WORKER_HEARTBEAT_TIMEOUT_SECONDS` | `30` seconds | Worker availability display |
| `WORKER_REQUEST_ATTEMPTS` | `3` | Bounded HTTP attempts |
| `MAX_SHARD_ATTEMPTS` | `3` | Bounded shard attempts |

No private IP address is hardcoded.

## Single-Computer Demo

Use four terminals from the repository root.

Terminal 1, coordinator:

```bash
make coordinator
```

Terminal 2, first worker:

```bash
make worker WORKER_ID=worker-a
```

Terminal 3, second worker:

```bash
make worker WORKER_ID=worker-b
```

Terminal 4, submit the job:

```bash
make submit-demo
```

The submission response includes the job ID and ends in `distributed`, ready for
worker claims. After both workers return results, inspect all jobs:

```bash
make demo-status
```

Or inspect one job:

```bash
make demo-status JOB_ID=job-xxxxxxxxxxxx
```

List registered workers:

```bash
make workers
```

## Two-Computer LAN Demo

Both computers must be on the same local network and checked out at the same
commit. The operating-system firewall may need to allow inbound TCP traffic to
port `8000` on Computer A.

### Computer A

Find its Wi-Fi LAN address on macOS:

```bash
ipconfig getifaddr en0
```

Start the coordinator on all interfaces:

```bash
COORDINATOR_HOST=0.0.0.0 COORDINATOR_PORT=8000 make coordinator
```

Equivalent direct command:

```bash
./.venv/bin/python -m uvicorn server.server:app --host 0.0.0.0 --port 8000
```

Optionally run the first worker on Computer A:

```bash
COORDINATOR_URL=http://127.0.0.1:8000 WORKER_ID=worker-a \
  ./.venv/bin/python -m client.worker
```

### Computer B

Replace `<COMPUTER_A_LAN_IP>` with the result from Computer A:

```bash
COORDINATOR_URL=http://<COMPUTER_A_LAN_IP>:8000 WORKER_ID=worker-b \
  ./.venv/bin/python -m client.worker
```

Check connectivity from Computer B before submitting a job:

```bash
curl http://<COMPUTER_A_LAN_IP>:8000/health
```

### Submit And Inspect

On Computer A:

```bash
COORDINATOR_URL=http://127.0.0.1:8000 make submit-demo
COORDINATOR_URL=http://127.0.0.1:8000 make demo-status
```

A successful job reports:

- `status: completed`
- two shards with different `worker_id` values
- `exact_match_count` equal to `sample_count`
- `mismatch_count: 0`
- identical `baseline_checksum` and `distributed_checksum`
- baseline and per-shard processing durations

The two shard records are the proof that both registered workers participated.
Each also records attempt count, timestamps, checksum, duration, and any error.

## Job Lifecycle

The successful lifecycle is:

```text
submitted -> sharded -> distributed -> processing -> verifying -> completed
```

`client.demo_client submit` creates a job and advances it to `distributed`.
The first claim moves it to `processing`. The final shard result triggers merge
and verification. A completed job stays completed if its advance endpoint is
called again. Integrity or exhausted-retry failures move the job to `failed`.

State is held in a thread-safe in-memory store. Restarting the coordinator clears
all jobs and worker registrations.

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Coordinator health and model version |
| `POST` | `/workers/register` | Register or refresh a worker |
| `GET` | `/workers` | Inspect workers and heartbeat status |
| `POST` | `/workers/{worker_id}/heartbeat` | Refresh worker heartbeat |
| `POST` | `/workers/{worker_id}/next-shard` | Atomically claim a shard; `204` if none |
| `POST` | `/workers/{worker_id}/results` | Submit success or failure metadata |
| `POST` | `/demo/prediction-jobs` | Create a deterministic job |
| `GET` | `/demo/prediction-jobs` | List in-progress, completed, and failed jobs |
| `GET` | `/demo/prediction-jobs/history` | Compatibility alias for job history |
| `GET` | `/demo/prediction-jobs/{job_id}` | Inspect one job |
| `POST` | `/demo/prediction-jobs/{job_id}/advance` | Advance a valid lifecycle stage |
| `POST` | `/predict` | Compatibility endpoint for direct inference |

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

## Verification

For every job, the coordinator first predicts the complete input on Computer A
and records its SHA-256 checksum and processing time. It then splits original
indexes into deterministic, non-overlapping shards.

A result is accepted only when:

1. The worker is registered and holds the active lease.
2. Returned indexes exactly match the shard with no duplicates.
3. Prediction and index counts match.
4. The reported checksum matches the returned predictions.

After every shard completes, the coordinator sorts by original index, rejects
missing or duplicated indexes, computes the distributed checksum, and compares
every prediction with the baseline. Any mismatch fails the job.

Duplicate submission of the same completed result is idempotent. Conflicting
duplicates are rejected. Expired leases can be claimed by another worker, and
worker-reported failures are retried up to `MAX_SHARD_ATTEMPTS`.

## Tests

Run the full suite:

```bash
make test
```

Equivalent command:

```bash
./.venv/bin/python -m pytest -q
```

The suite covers the existing clinical and file-based behavior plus worker
registration, lifecycle order, atomic claims, two distinct workers, exact
baseline matching, ordered merge, malformed and unknown results, duplicate
idempotency, lease expiration, checksum failure, and worker-failure isolation.

At the time of this implementation, the local result is:

```text
52 passed
```

## Troubleshooting

**Computer B cannot reach `/health`:** confirm both machines are on the same
network, use Computer A's LAN IP rather than `127.0.0.1`, and permit port `8000`
through the firewall.

**Worker receives `404 Unknown worker ID`:** restart the worker so it registers,
or call `/workers/register` before worker-specific routes.

**Worker repeatedly receives `204`:** ensure a job exists and has advanced to
`distributed`. Check `make demo-status` and `make workers`.

**Job remains in `processing`:** inspect shard errors and worker heartbeat times.
An abandoned lease becomes eligible for reassignment after
`SHARD_LEASE_SECONDS`.

**Model version mismatch:** update both machines to the same commit, recreate the
virtual environments, and run `make install` on both.

**Checksum mismatch:** inspect the failed shard's indexes, predictions, and model
version. The coordinator records the reported and calculated checksum in the job
errors.

## Current Limitations

- Physical two-computer LAN validation is still pending; automated two-worker
  integration tests pass on one machine.
- The coordinator is centralized and in-memory with no authentication or TLS.
- Workers poll over HTTP; there is no push channel or peer discovery.
- Every process trains the small deterministic model at startup.
- Jobs use the built-in digits dataset and two shards by default.
- Restarting the coordinator clears jobs and registered workers.
- The separate clinical workspace remains a simulated product demo and is not
  executed by these physical workers.

## Future Work

After a successful physical LAN rehearsal, useful next steps are durable job
storage, authenticated worker enrollment, TLS, artifact/model distribution,
lease observability, and broader fault-injection testing. A decentralized mesh
would require a separate architecture and is intentionally outside this proof of
concept.

Clinical product-demo documentation remains in
[`clinical/README.md`](clinical/README.md), and sprint boundaries remain in
[`BIOSTONK_IMPLEMENTATION_GUIDE.md`](BIOSTONK_IMPLEMENTATION_GUIDE.md).
