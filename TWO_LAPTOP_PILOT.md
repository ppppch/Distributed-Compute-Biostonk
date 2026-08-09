# BioStonk Two-Laptop LAN Pilot

This runbook validates a **pre-production LAN pilot**, not a finished product or
production hardware approval system. It proves that two distinct laptops can
pull replicated Trial2Vec comparison tasks, execute the same artifact bundle,
return matching canonical checksums, and produce one aggregate result.

It does not yet provide mutual TLS, certificate-backed device identity,
sandboxing, persistent jobs, encrypted task payloads, tenant isolation, or
hardware attestation. Use synthetic or public demo data only. Do not use PHI,
customer protocols, credentials, or confidential documents over this HTTP pilot.

## Pilot Topology

- **Laptop A:** coordinator, dashboard, and worker `laptop-a`
- **Laptop B:** worker `laptop-b`
- Both laptops must be on the same trusted LAN and have different hostnames.
- Both laptops must have the same code and comparison artifacts.

Required matching artifacts:

- `clinical/data/trials.npz`
- every `.xlsx` file in `clinical/data/Emde/`
- `clinical/data/trial_metadata.json`, when present

## 1. Prepare Both Laptops

Use the same repository revision and copy the generated local artifacts listed
above to the same relative paths on both laptops. Then, on each laptop:

```bash
cd /path/to/Biostonk
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r clinical/requirements.txt
```

Run preflight on Laptop A:

```bash
WORKER_ID=laptop-a .venv/bin/python -m client.clinical_worker --preflight
```

Run preflight on Laptop B:

```bash
WORKER_ID=laptop-b .venv/bin/python -m client.clinical_worker --preflight
```

The two printed `artifact_checksum` values must match. The printed `hostname`
values must differ. Stop if either condition fails.

## 2. Find Laptop A's LAN Address

On Laptop A, try:

```bash
ipconfig getifaddr en0
```

If that is blank, inspect other interfaces with:

```bash
ifconfig | grep "inet "
```

Use the private LAN address, commonly `192.168.x.x` or `10.x.x.x`. The examples
below use `192.168.1.20`; replace it with Laptop A's actual address.

## 3. Start the Strict Coordinator on Laptop A

```bash
cd /path/to/Biostonk
BIOSTONK_APPROVED_WORKERS=laptop-a,laptop-b \
BIOSTONK_REQUIRE_DISTINCT_HOSTS=true \
.venv/bin/python -m uvicorn clinical.api:app --host 0.0.0.0 --port 8001
```

Allow incoming Python connections if macOS displays a firewall prompt. Keep this
terminal running. Do not use `--reload`; a restart clears in-memory jobs and
worker registrations.

## 4. Start Worker A on Laptop A

In a second Laptop A terminal:

```bash
cd /path/to/Biostonk
WORKER_ID=laptop-a \
COORDINATOR_URL=http://127.0.0.1:8001 \
.venv/bin/python -m client.clinical_worker
```

## 5. Verify Connectivity from Laptop B

On Laptop B:

```bash
curl http://192.168.1.20:8001/health
```

Expected response:

```json
{"status":"ok"}
```

If it fails, verify both laptops are on the same LAN, confirm Laptop A's address,
and allow inbound TCP port `8001` in the macOS firewall. Do not expose this HTTP
pilot directly to the public internet.

## 6. Start Worker B on Laptop B

```bash
cd /path/to/Biostonk
WORKER_ID=laptop-b \
COORDINATOR_URL=http://192.168.1.20:8001 \
.venv/bin/python -m client.clinical_worker
```

## 7. Confirm Two-Host Readiness

From either laptop:

```bash
curl http://192.168.1.20:8001/compute/readiness
```

The response must include:

```json
{
  "ready": true,
  "mode": "two-host-lan-pilot",
  "production_ready": false,
  "active_worker_count": 2,
  "distinct_active_host_count": 2,
  "blockers": []
}
```

The dashboard submit button remains disabled until this readiness check passes.

## 8. Run the Comparison

On Laptop A, open:

```text
http://127.0.0.1:8001
```

Upload or paste a public demo protocol, select the known NCT anchor, and run the
comparison. Keep both worker terminals visible during the run.

## 9. Pilot Pass Criteria

The pilot passes only when all of the following are true:

1. Readiness reports two active workers and two distinct hostnames.
2. Each worker terminal reports one replica result submission.
3. The job reaches `completed` without retries or errors.
4. The dashboard reports `independent replica agreement`.
5. The verification manifest reports `distinct_host_count: 2`.
6. Both task checksums match and one `aggregate_checksum` is present.
7. Exactly one aggregate comparison result is returned.

Inspect the latest job directly if needed:

```bash
curl http://127.0.0.1:8001/comparison-jobs/history
```

## Failure Meaning

- **Readiness blocked:** a worker is missing, inactive, on the same hostname, or
  not registered.
- **Registration rejected:** worker ID, workload version, or artifact bundle does
  not match coordinator policy.
- **Replica verification failed:** workers returned different result payloads;
  do not use the aggregate.
- **Worker unavailable:** check the coordinator URL, firewall, Wi-Fi isolation,
  and whether Laptop A restarted.

Passing this runbook establishes a two-laptop orchestration and deterministic
verification milestone. It does not establish production security, regulatory
validation, clinical validity, or approved-hardware identity.