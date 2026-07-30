"""
Step 6: Combine results from both chunks and verify against baseline.

Loads both computers' results, reassembles them in the ORIGINAL
order (using original_index), then recomputes the fingerprint and
checks it against the single-computer baseline.
"""

import json
import hashlib
import numpy as np

def main():
    #loads both chunks results
    part1 = np.load("results_part1.npz")
    part2 = np.load("results_part2.npz")

    #stack everything together: predictions and their original positions
    all_predictions = np.concatenate([part1["predictions"], part2["predictions"]])
    all_indices = np.concatenate([part1["original_index"], part2["original_index"]])

    #sort by original_index so everything lines up
    sort_order = np.argsort(all_indices)
    combined_predictions = all_predictions[sort_order]

    #recalc the fingerprint, how the baseline did
    combined_hash = hashlib.sha256(combined_predictions.tobytes()).hexdigest()

    #load the baseline's report to compare against
    with open("baseline_report.json") as f:
        baseline_report = json.load(f)
    baseline_hash = baseline_report["prediction_hash_sha256"]

    print(f"Baseline hash:    {baseline_hash}")
    print(f"Distributed hash: {combined_hash}")

    if combined_hash == baseline_hash:
        print("MATCH - distributed results are identical to the baseline.")
    else:
        print("MISMATCH - something differs from the baseline.")

if __name__ == "__main__":
    main()