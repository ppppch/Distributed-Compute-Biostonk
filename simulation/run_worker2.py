"""
Step 5B: Run inference on the other chunk (SIMULATING COMPUTER 2).

Same idea as run_worker1.py, but this one only knows about
job_part2.npz. In the real two-computer version, this would be
a completely separate machine with no access to Part 1's data.
"""

import numpy as np
import joblib

def main():
    model = joblib.load("baseline_model.joblib") #loads model
    data = np.load("job_part2.npz")
    X_part, original_index = data["X"], data["original_index"]

    predictions = model.predict(X_part) #runs inference

    np.savez("results_part2.npz", predictions=predictions, original_index=original_index)

    print(f"Processed {X_part.shape[0]} samples (Part 2)")

if __name__ == "__main__":
    main()