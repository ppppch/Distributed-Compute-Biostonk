"""
Client computer - processes its own local chunk.

Loads the model and runs inference on job_part1.npz. 
job_part2.npz gets sent to the server instead (handled by
send_to_server.py).
"""

import numpy as np
import joblib

def main():
    #same frozen model,
    model = joblib.load("../shared/baseline_model.joblib")

    #this computer's own chunk, processed locally, no connections used
    data = np.load("job_part1.npz")
    X_part, original_index = data["X"], data["original_index"]

    predictions = model.predict(X_part)

    np.savez("results_part1.npz", predictions=predictions, original_index=original_index)

    print(f"Processed {X_part.shape[0]} samples locally (Part 1)")

if __name__ == "__main__":
    main()