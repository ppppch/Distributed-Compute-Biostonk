# Week 1 Research Summary

## What was built

End-to-end local simulation of distributed ML inference on the scikit-learn
digits dataset:

1. `prepare_dataset.py` — splits 1,797 labeled images into `train.npz` (1,257)
   and `job.npz` (540).
2. `train_model.py` — trains a `RandomForestClassifier` and saves
   `baseline_model.joblib`.
3. `run_baseline.py` — runs inference on the full job set and writes a SHA-256
   fingerprint to `baseline_report.json`.
4. `split_job.py` — divides `job.npz` into two chunks while preserving
   `original_index`.
5. `run_worker.py` — single reusable worker script that loads the same frozen
   model and predicts on one chunk at a time (replaces `run_worker1.py` /
   `run_worker2.py`).
6. `combine_and_verify.py` — reassembles predictions by `original_index`,
   recomputes the fingerprint, and checks it against the baseline.

## Verification result

```text
$ python3 combine_and_verify.py
Baseline hash:    a4b7968caf3ccc0f397d81d2ed7e4acbedf7fec14c86596e4a116b1172ceadd4
Distributed hash: a4b7968caf3ccc0f397d81d2ed7e4acbedf7fec14c86596e4a116b1172ceadd4
MATCH - distributed results are identical to the baseline.
```

Baseline accuracy: 0.9667 on 540 samples.

## Current branch state

- Branch: `maggie/week-1-research`
- Source implementation is complete and even with `main`.
- Generated artifacts are present in the working tree but are not tracked.

## Open decision for next iteration

- **Option A:** Keep the local file-based simulation and focus on code quality
  (tests, refactoring duplicated worker scripts, CI).
- **Option B:** Move toward real distributed compute by adding a networked
  coordinator/worker protocol, worker discovery, fault tolerance, and dynamic
  scaling.
