"""
Step 2: Train the baseline model.

Loads the training data and uses it to build a small model that can
recognize handwritten digits. Saves the trained model to a file so
every later script (including runs on the two computers) uses this
exact same model.

Creates baseline_model.joblib which is the model, or the result
containing specific learned patterns.
"""

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier #imports the algorithm

RANDOM_SEED = 42

def main():
    data = np.load("train.npz")
    X_train, y_train = data["X"], data["y"]

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(X_train, y_train) #training

    joblib.dump(model, "baseline_model.joblib") #a trained model, able to recognize the learned patterns
    print("Model trained and saved to baseline_model.joblib")

if __name__ == "__main__":
    main()