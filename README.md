# Distributed MNIST Digit Inference

This project runs handwritten-digit inference across **two real machines**:

- **Server computer** — hosts the trained model and answers prediction requests over HTTP.
- **Client computer** — splits the job, processes half locally, sends the other half to the server, and verifies the combined result.

The old two-file simulation in `simulation/` is no longer used; it’s just kept for reference.

Clinical-trial embedding data can be imported through [clinical/README.md](clinical/README.md).

---

## What you need first

Install these on whichever computer runs the baseline and the client:

```bash
pip install requests numpy scikit-learn joblib
```

The server only needs:

```bash
pip install fastapi uvicorn scikit-learn numpy joblib firebase-admin
```

(or run `pip install -r server/requirements.txt` from the server folder).

### Firebase audit (optional)

The server can write a small audit record for each inference request to the
Firestore project `civicgrid-e8b69`. The prediction path never reads Firestore:
each request writes one `inference_jobs` document at start and updates it at
completion. Images and predictions are not stored in Firestore.

Create a Firestore database in the CivicGrid Firebase console, then authenticate
the server with Application Default Credentials or a service-account key kept
outside this repository. Enable the audit when starting the server:

```bash
export FIRESTORE_AUDIT_ENABLED=true
export FIREBASE_PROJECT_ID=civicgrid-e8b69
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/service-account.json
uvicorn server:app --host 0.0.0.0 --port 8000
```

This design uses **0 Firestore reads per inference job**. Avoid listeners,
collection queries, and polling the job document; use the synchronous `/predict`
response instead. At 50,000 inference jobs, it remains at 0 reads and uses
100,000 Firestore writes.

---

## Step 0: Build the baseline

On **one** computer (it can be the client, the server, or a third machine), run:

```bash
make baseline
```

You should see output like this:

```
Train set: 1257 samples -> train.npz
Job set:   540 samples -> job.npz
Model trained and saved to baseline_model.joblib
Processed 540 samples in ...
Accuracy: 0.9667
Fingerprint (hash): a4b7968caf3ccc0f397d81d2ed7e4acbedf7fec14c86596e4a116b1172ceadd4
Baseline pipeline complete. Model saved to shared/baseline_model.joblib
```

This creates three things you need for the distributed run:

- `shared/baseline_model.joblib` — the trained model
- `baseline/job.npz` — the 540 images that will be split across machines
- `baseline/baseline_report.json` — the answer key/hash

---

## Quick test: one computer, two terminals

You can test the whole two-machine flow on a single computer using two terminal windows.

### Terminal 1 — start the server

```bash
cd server
uvicorn server:app --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this running.

### Terminal 2 — run the client

From the project root:

```bash
make split
make worker_local
cd client
python3 send_to_server.py --url http://127.0.0.1:8000/predict
python3 combine_and_verify.py
```

Expected final output:

```
Sent 270 samples to http://127.0.0.1:8000/predict (Part 2)
Baseline hash:    a4b7968caf3ccc0f397d81d2ed7e4acbedf7fec14c86596e4a116b1172ceadd4
Distributed hash: a4b7968caf3ccc0f397d81d2ed7e4acbedf7fec14c86596e4a116b1172ceadd4
MATCH - distributed results are identical to the baseline.
```

The hash on your machine may be different, but the important part is `MATCH`.

To stop the server, go back to Terminal 1 and press `Ctrl + C`.

---

## Real test: two separate computers

### Computer A — the server

1. Copy these to the server computer, keeping the same folder layout:

   ```
   server/
   shared/baseline_model.joblib
   ```

   So the server folder looks like:

   ```
   server/
     server.py
     requirements.txt
   shared/
     baseline_model.joblib
   ```

2. Install server dependencies:

   ```bash
   cd server
   pip install -r requirements.txt
   ```

3. Start the server:

   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```

   Note the server’s IP address (for example, `192.168.1.50`).

### Computer B — the client

1. Copy these to the client computer, keeping the same folder layout:

   ```
   client/
   baseline/
   shared/baseline_model.joblib
   Makefile
   ```

   So the client folder looks like:

   ```
   client/
     split_job.py
     run_worker_local.py
     send_to_server.py
     combine_and_verify.py
   baseline/
     job.npz
     baseline_report.json
   shared/
     baseline_model.joblib
   Makefile
   ```

2. Install client dependencies:

   ```bash
   pip install requests numpy scikit-learn joblib
   ```

3. Run the client pipeline. Replace `<server-ip>` with the server’s actual IP:

   ```bash
   make split
   make worker_local
   cd client
   python3 send_to_server.py --url http://<server-ip>:8000/predict
   python3 combine_and_verify.py
   ```

   Example:

   ```bash
   python3 send_to_server.py --url http://192.168.1.50:8000/predict
   ```

4. You should see:

   ```
   Sent 270 samples to http://192.168.1.50:8000/predict (Part 2)
   Baseline hash:    ...
   Distributed hash: ...
   MATCH - distributed results are identical to the baseline.
   ```

---

## What each file does

| File | Purpose |
|---|---|
| `baseline/prepare_dataset.py` | Splits raw digits into `train.npz` and `job.npz` |
| `baseline/train_model.py` | Trains the model and saves it to `shared/baseline_model.joblib` |
| `baseline/run_baseline.py` | Runs inference on the full job and creates `baseline_report.json` (the answer key) |
| `server/server.py` | FastAPI server that loads the model and exposes `POST /predict` |
| `client/split_job.py` | Splits `job.npz` into `job_part1.npz` and `job_part2.npz` |
| `client/run_worker_local.py` | Processes `job_part1.npz` locally, saves `results_part1.npz` |
| `client/send_to_server.py` | Sends `job_part2.npz` to the server, saves `results_part2.npz` |
| `client/combine_and_verify.py` | Combines both result files and checks the fingerprint |

---

## Using the server API directly

`POST /predict`

Request body:

```json
{
  "images": [[0.0, 1.0, ...], ...],
  "original_index": [0, 1, ...]
}
```

Response:

```json
{
  "predictions": [3, 7, ...],
  "original_index": [0, 1, ...]
}
```

Quick curl test:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"images": [[0.0, 0.0, ...]], "original_index": [0]}'
```

---

## Makefile targets

```bash
make baseline      # full single-computer baseline
make prepare       # split raw data
make train         # train and save the model
make baseline_run  # run single-computer inference
make split         # split job.npz into two chunks
make worker_local  # run the local client worker (Part 1)
make test          # run Maggie's unit and integration tests
make clean         # delete all generated files
```

---

## About `simulation/`

`simulation/run_worker1.py` and `simulation/run_worker2.py` are the old
single-computer simulation. They pretended to be two separate machines by
reading two different `.npz` files in the same filesystem. The project now uses
the real server/client code in `server/` and `client/`.

The original root-level scripts and Maggie's tests are also retained for
compatibility. Run `make legacy-baseline`, then `make legacy-workers` to use the
local simulation path.
