# Distributed MNIST Digit Inference (real two-machine setup)

This repo is moving from a single-computer baseline and an old two-file simulation
to a real network-based, two-machine pipeline:

- **Server machine** — runs `server/server.py`, a FastAPI service that loads the
trained model once and answers `POST /predict` requests over HTTP.
- **Client machine** — runs the scripts in `client/`. It splits the job, processes
half locally, sends the other half to the server, then reassembles and verifies
both halves against the single-computer baseline.

> **Note:** `simulation/` contains the old two-file simulation and is no longer
> part of the main workflow.

---

## Project layout

```
baseline/
  prepare_dataset.py   # splits raw data into train.npz + job.npz
  train_model.py       # trains the model and saves it to shared/
  run_baseline.py      # single-computer inference, creates baseline_report.json

shared/
  baseline_model.joblib   # the trained model used by both machines

server/
  server.py            # FastAPI inference server
  requirements.txt     # server dependencies

client/
  split_job.py         # splits job.npz into job_part1.npz + job_part2.npz
  run_worker_local.py  # processes job_part1.npz on the client machine
  send_to_server.py    # sends job_part2.npz to the remote server
  combine_and_verify.py # reassembles results and checks the fingerprint

simulation/            # OLD simulated two-computer code (kept for reference)
```

---

## How to run

### 1. Build the baseline on one machine

```
make baseline
```

This runs `prepare_dataset.py` → `train_model.py` → `run_baseline.py` and
produces:

- `baseline/train.npz` and `baseline/job.npz`
- `shared/baseline_model.joblib`
- `baseline/baseline_report.json` (the answer key, including the prediction hash)

### 2. Run the two-machine distributed pipeline

You need the trained model on the server machine and the job data on the client
machine. Both machines should share the same repo layout (so `server.py` can find
`../shared/baseline_model.joblib`).

**On the server machine:**

```
cd server
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

**On the client machine:**

```
make split
make worker_local
cd client && python3 send_to_server.py --url http://<server-ip>:8000/predict
python3 combine_and_verify.py
```

- `make split` creates `client/job_part1.npz` and `client/job_part2.npz`.
- `make worker_local` runs inference on Part 1 locally and saves
  `client/results_part1.npz`.
- `send_to_server.py` posts Part 2 to the server and saves
  `client/results_part2.npz`.
- `combine_and_verify.py` reassembles both parts in original order and compares
  the combined fingerprint to `baseline/baseline_report.json`.

If you are testing on one computer, use two terminal windows and replace
`<server-ip>` with `127.0.0.1`.

### Files that need to exist on each machine

- **Server machine:** `server/` plus `shared/baseline_model.joblib` (the trained
  model). `server.py` loads the model from `../shared/baseline_model.joblib`.
- **Client machine:** `client/`, `shared/baseline_model.joblib` (for the local
  worker), and the contents of `baseline/` (`job.npz` and
  `baseline_report.json`). The client scripts expect `baseline/` to sit next to
  `client/`, matching the repo layout.

On a real second machine you can copy just those folders; you do not need to
rerun the baseline training on the client.

### Makefile targets

```
make baseline        # full single-computer baseline
make prepare         # split raw data
make train           # train and save the model
make baseline_run    # run single-computer inference
make split           # split job.npz into two chunks
make worker_local    # run the local client worker (Part 1)
make clean           # delete all generated files
```

`send_to_server.py` is run directly because it needs the server's URL as an
argument. The client also needs `requests` installed (`pip install requests`)
alongside the baseline packages (`numpy`, `scikit-learn`, `joblib`).

---

## How the data moves

### Stage 1: Raw data exists

**1,797 handwritten digit images**, each one already labeled with its correct answer.

↓

### Stage 2: Split into two piles (`baseline/prepare_dataset.py`)

```
1,797 images
      │
      ├──► 1,257 images → train.npz  (for teaching the model)
      │
      └──►   540 images → job.npz    (for testing/running the model)
```

↓

### Stage 3: Choose an algorithm (`baseline/train_model.py`)

```python
from sklearn.ensemble import RandomForestClassifier
```

↓

### Stage 4: Training — algorithm + data → model

```python
model = RandomForestClassifier(...)
model.fit(X_train, y_train)
joblib.dump(model, "../shared/baseline_model.joblib")
```

The model is trained once and reused everywhere after that.

↓

### Stage 5: Baseline inference — model + job data → predictions

`baseline/run_baseline.py`:

```python
model = joblib.load("../shared/baseline_model.joblib")
predictions = model.predict(X_job)
```

It also computes accuracy and a SHA-256 fingerprint of the predictions, saved in
`baseline/baseline_report.json`. That fingerprint is the answer key.

↓

### Stage 6: Split the job into two chunks (`client/split_job.py`)

```
job.npz (540 images)
      │
      ├──► 270 images → job_part1.npz  (client machine)
      │
      └──► 270 images → job_part2.npz  (sent to server)
```

Each chunk keeps its `original_index` so the results can be reordered later.

↓

### Stage 7: Distributed inference across two machines

- **Client machine** (`client/run_worker_local.py`) loads the model and runs
  inference on `job_part1.npz`, saving `results_part1.npz`.
- **Server machine** (`server/server.py`) receives `job_part2.npz` over HTTP,
  runs inference, and returns the predictions.
- **Client machine** (`client/send_to_server.py`) posts Part 2 and saves the
  response as `results_part2.npz`.

Both machines use the exact same frozen model (`baseline_model.joblib`), so the
only difference is *which slice* of data they predict on.

↓

### Stage 8: Combine + verify (`client/combine_and_verify.py`)

```python
combined_predictions = all_predictions[sort_order]
combined_hash = hashlib.sha256(combined_predictions.tobytes()).hexdigest()
```

The two result files are stitched back together, sorted by `original_index`, and
re-fingerprinted. If `combined_hash == baseline_hash`, the distributed pipeline
produced results identical to the single-computer baseline.

---

## Putting it all on one line

```
Raw labeled images
   → split into TRAIN data + JOB data
       → TRAIN data + algorithm → (training) → trained MODEL
           → trained MODEL + JOB data → (inference) → predictions
               → predictions vs real answers → accuracy + fingerprint (baseline)

JOB data → split into PART 1 + PART 2
   → trained MODEL + PART 1 → predictions 1  ─┐
   → trained MODEL + PART 2 → predictions 2  ─┴─► combine (in order) → fingerprint
                                                        → compare to baseline fingerprint
```

---

## The key mental model to walk away with

| Term | What it is | When it's used |
|---|---|---|
| **Dataset** | Raw labeled examples | Exists before anything runs |
| **Algorithm** | The general learning method | Imported, empty, reusable |
| **Training** | Algorithm + labeled data → patterns | Happens once (`fit()`) |
| **Model** | The saved, specific result of training | Created once, reused forever after |
| **Inference** | Model + new unlabeled data → predictions | Happens every time you `predict()` — this is what you're distributing |
| **Verification** | Predictions vs. real answers | Happens after inference, to check correctness |
| **Chunk / part** | A slice of the job data | Created in Stage 6, one per machine |
| **Worker** | A script that runs inference on one chunk | `run_worker_local.py` on the client, `server.py` on the server |
| **Combine + verify** | Reassembling chunks and re-checking the fingerprint | Proves the distributed result matches the single-computer baseline |

---

## About the `simulation/` folder

`simulation/run_worker1.py` and `simulation/run_worker2.py` are the old
single-computer simulation. They pretended to be two separate machines by
reading two different `.npz` files in the same filesystem. That approach was
useful for proving the idea, but the project is now moving to a real
server/client setup in `server/` and `client/`.
