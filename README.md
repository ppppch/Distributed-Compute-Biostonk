# Distributed MNIST Digit Inference

This project runs handwritten-digit inference across **two real machines**:

- **Server computer** — hosts the trained model and answers prediction requests over HTTP.
- **Client computer** — splits the job, processes half locally, sends the other half to the server, and verifies the combined result.

The old two-file simulation in `simulation/` is no longer used; it’s just kept for reference.

---

## What each part does

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

## How to run

### 1. Build the baseline (on one computer)

```bash
make baseline
```

This produces:

- `baseline/job.npz` — the 540 images to distribute
- `baseline/baseline_report.json` — the answer key/hash
- `shared/baseline_model.joblib` — the trained model

### 2. Set up the server computer

Copy `server/` and `shared/baseline_model.joblib` to the server.

```bash
cd server
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

The server is now listening at `http://<server-ip>:8000`.

### 3. Set up the client computer

Copy `client/` and `shared/baseline_model.joblib` to the client.
Also copy `baseline/job.npz` and `baseline/baseline_report.json` so the client can split and verify.

Install the client dependencies:

```bash
pip install requests numpy scikit-learn joblib
```

Run the client pipeline:

```bash
make split
make worker_local
cd client
python3 send_to_server.py --url http://<server-ip>:8000/predict
python3 combine_and_verify.py
```

If you are testing on one computer, use two terminal windows and replace `<server-ip>` with `127.0.0.1`.

---

## Using the pieces directly

### Server endpoint

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

You can test it with curl:

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"images": [[0.0, 0.0, ...]], "original_index": [0]}'
```

### Client scripts

```bash
# split the job into two chunks
cd client && python3 split_job.py

# process part 1 locally
cd client && python3 run_worker_local.py

# send part 2 to the server
cd client && python3 send_to_server.py --url http://<server-ip>:8000/predict

# combine and verify against the baseline
cd client && python3 combine_and_verify.py
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
make clean         # delete all generated files
```

---

## About `simulation/`

`simulation/run_worker1.py` and `simulation/run_worker2.py` are the old
single-computer simulation. They pretended to be two separate machines by
reading two different `.npz` files in the same filesystem. The project now uses
the real server/client code in `server/` and `client/`.
