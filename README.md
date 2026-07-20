# How to Run
```
make baseline
```
Runs the single-computer phase, in order: `prepare_dataset.py` → `train_model.py` → `run_baseline.py`. Produces the baseline answer key (`baseline_report.json`), including the fingerprint hash.

```
make workers
```
Runs the distributed (simulated) phase, in order: `split_job.py` → `run_worker.py` (twice, once per chunk). Splits the job into two chunks and processes each one independently, as if on two separate computers.

```
make clean
```
Deletes every generated file (`.npz`, `.joblib`, `.json`).

```
make test
```
Runs the unit and integration tests in `tests/`.

You can also run any single step on its own:

```
make prepare
make train
make baseline_run
make split
make worker1
make worker2
make test
```

**Typical full run, start to finish:**
```
make baseline
make workers
python3 combine_and_verify.py
```


# How the Data Moves
### Stage 1: Raw data exists

**1,797 handwritten digit images**, each one already labeled with its correct answer (a real person confirmed "this is a 3," etc.)

↓

### Stage 2: Split into two piles (`prepare_dataset.py`)

```
1,797 images
      │
      ├──► 1,257 images → train.npz  (for teaching the model)
      │
      └──►   540 images → job.npz    (for testing/running the model)
```

At this point, nothing has been "learned" yet — this is purely organizing raw data.

↓

### Stage 3: Choose an algorithm (`train_model.py`, import line)

```python
from sklearn.ensemble import RandomForestClassifier
```

This brings in the **method** for learning. It's an empty, reusable process. It knows nothing about digits yet.

↓

### Stage 4: Training — algorithm + data → model

```python
model = RandomForestClassifier(...)      # empty structure, using the algorithm
model.fit(X_train, y_train)              # THE ACTUAL LEARNING HAPPENS HERE
```

This is the one moment where **data** and **algorithm** combine:

- **Input:** 1,257 images (`X_train`) + their correct answers (`y_train`)
- **Process:** the algorithm looks for patterns that connect pixel arrangements to digits
- **Output:** a **trained model** — no longer empty, now full of learned patterns

```python
joblib.dump(model, "baseline_model.joblib")
```

That model gets saved to a file. From this point forward, this file **is** the model. It is reusable, and never retrained again in this project.

↓

### Stage 5: Inference — model + new data → predictions (`run_baseline.py`)

```python
model = joblib.load("baseline_model.joblib")   # load the frozen, trained model
data = np.load("job.npz")
X_job, y_job = data["X"], data["y"]
predictions = model.predict(X_job)              # INFERENCE HAPPENS HERE
```

- **Input:** the trained model + 540 *new* images (`X_job`) — notice, no answers given this time
- **Process:** the model applies the patterns it already learned, and guesses each digit
- **Output:** 540 predictions

↓

### Stage 6: Verification — checking the guesses (baseline)

```python
accuracy = (predictions == y_job).mean()          # compare guesses to real answers
pred_hash = hashlib.sha256(predictions.tobytes())  # fingerprint the guesses
```

This is the only place `y_job` (the real answers for the job data) actually gets used — to grade the model afterwards. The resulting hash becomes the **answer key** for the distributed phase below.

↓

### Stage 7: Split the job into two chunks (`split_job.py`)

```
job.npz (540 images)
      │
      ├──► 270 images → job_part1.npz  (simulated Computer 1)
      │
      └──► 270 images → job_part2.npz  (simulated Computer 2)
```

Each chunk also stores its `original_index` — the position each image held in the original 540 — so the results can be put back in the correct order later.

↓

### Stage 8: Distributed inference — same model, two chunks (`run_worker.py`)

```python
# run_worker.py is invoked once per chunk with different input/output paths.
model = joblib.load("baseline_model.joblib")   # the SAME frozen model, no retraining
data = np.load("job_part1.npz")                # only this chunk -- no knowledge of the other
predictions = model.predict(data["X"])          # INFERENCE, run independently per chunk
```

- Each worker script only ever sees its own chunk — this simulates two separate computers that can't see each other's data
- Both use the exact same `baseline_model.joblib` file, so there's nothing different about *how* they predict — only *which slice* of data they're predicting on
- Each saves its own predictions **plus** `original_index`, so order can be restored later

↓

### Stage 9: Combine + verify (`combine_and_verify.py`)

```python
combined_predictions = all_predictions[sort_order]                       # reorder using original_index
combined_hash = hashlib.sha256(combined_predictions.tobytes()).hexdigest()
```

- Both chunks' predictions are stitched back together, sorted by `original_index` so they're in the exact same order as the original baseline run
- The fingerprint is recomputed the same way it was in Stage 6
- If `combined_hash == baseline_hash` → the distributed pipeline produced results **identical** to the single-computer baseline

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

## The key mental model to walk away with

| Term | What it is | When it's used |
|---|---|---|
| **Dataset** | Raw labeled examples | Exists before anything runs |
| **Algorithm** | The general learning method | Imported, empty, reusable |
| **Training** | Algorithm + labeled data → patterns | Happens once (`fit()`) |
| **Model** | The saved, specific result of training | Created once, reused forever after |
| **Inference** | Model + new unlabeled data → predictions | Happens every time you `predict()` — this is what you're distributing |
| **Verification** | Predictions vs. real answers | Happens after inference, to check correctness |
| **Chunk / part** | A slice of the job data | Created in Stage 7, one per simulated computer |
| **Worker** | A script that runs inference on one chunk only | Simulates one computer's independent piece of work |
| **Combine + verify** | Reassembling chunks in order and re-checking the fingerprint | Proves the distributed result matches the single-computer baseline |

---