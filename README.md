# Distributed Inference Project — How the Data Flows

This document walks through the full journey of the project, start to finish, with every term tied to exactly where it shows up in the code.

## The complete data flow

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

This brings in the **method** for learning — an empty, reusable process. It knows nothing about digits yet. It's the same import you'd use for a completely different dataset.

↓

### Stage 4: Training — algorithm + data → model

```python
model = RandomForestClassifier(...)      # empty structure, using the algorithm
model.fit(X_train, y_train)              # ← THE ACTUAL LEARNING HAPPENS HERE
```

This is the one moment where **data** and **algorithm** combine:

- **Input:** 1,257 images (`X_train`) + their correct answers (`y_train`)
- **Process:** the algorithm looks for patterns that connect pixel arrangements to digits
- **Output:** a **trained model** — no longer empty, now full of learned patterns

```python
joblib.dump(model, "baseline_model.joblib")
```

That model gets saved to a file. From this point forward, this file **is** the model — frozen, reusable, and never retrained again in your project.

↓

### Stage 5: Inference — model + new data → predictions (`run_baseline.py`)

```python
model = joblib.load("baseline_model.joblib")   # load the frozen, trained model
data = np.load("job.npz")
X_job, y_job = data["X"], data["y"]
predictions = model.predict(X_job)              # ← INFERENCE HAPPENS HERE
```

- **Input:** the trained model + 540 *new* images (`X_job`) — notice, no answers given this time
- **Process:** the model applies the patterns it already learned, and guesses each digit
- **Output:** 540 predictions

↓

### Stage 6: Verification — checking the guesses

```python
accuracy = (predictions == y_job).mean()          # compare guesses to real answers
pred_hash = hashlib.sha256(predictions.tobytes())  # fingerprint the guesses
```

This is the only place `y_job` (the real answers for the job data) actually gets used — purely to grade the model afterward, never during prediction itself.

---

## Putting it all on one line

```
Raw labeled images
   → split into TRAIN data + JOB data
       → TRAIN data + algorithm → (training) → trained MODEL
           → trained MODEL + JOB data → (inference) → predictions
               → predictions vs real answers → accuracy + fingerprint
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

This is also exactly why your project is called *distributed **inference*** and not distributed training — you're only splitting up Stage 5 (running the frozen model on data) across two computers. Stages 1–4 (data prep and training) only ever happen once, on one machine, before any distribution even begins.