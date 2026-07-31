"""
Step 5A: Run inference on one chunk (SIMULATING COMPUTER 1).

Loads the trained model and ONLY this chunk of the job data.
Pretend this script is running on a separate machine that has
no knowledge of the other chunk.
"""

import numpy as np
import joblib

def main():
    model = joblib.load("baseline_model.joblib") #loads model
    data = np.load("job_part1.npz")
    X_part, original_index = data["X"], data["original_index"]

    predictions = model.predict(X_part) #runs inference

    np.savez("results_part1.npz", predictions=predictions, original_index=original_index)

    print(f"Processed {X_part.shape[0]} samples (Part 1)")

if __name__ == "__main__":
    main()