"""
Step 3: Run the single-computer baseline.

Loads the trained model and runs it on the FULL job dataset, all on
this one computer. Saves the results, timing, and a fingerprint
(hash) of the predictions -- this becomes the "answer key" we compare
the distributed version against later.


"""

import time
import json
import hashlib
import numpy as np
import joblib

def main():
    model = joblib.load("baseline_model.joblib")
    data = np.load("job.npz")
    X_job, y_job = data["X"], data["y"]

    start = time.perf_counter()
    predictions = model.predict(X_job)
    elapsed = time.perf_counter() - start

    accuracy = float((predictions == y_job).mean())
    pred_hash = hashlib.sha256(predictions.tobytes()).hexdigest()

    np.savez("baseline_predictions.npz", predictions=predictions, true_labels=y_job)

    report = {
        "num_samples": int(X_job.shape[0]),
        "elapsed_seconds": elapsed,
        "accuracy": accuracy,
        "prediction_hash_sha256": pred_hash,
    }
    with open("baseline_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Processed {report['num_samples']} samples in {elapsed:.4f}s")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Fingerprint (hash): {pred_hash}")

if __name__ == "__main__":
    main()