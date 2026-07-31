"""
Step 1: Prepare the dataset.

Loads a small built-in dataset (handwritten digit images) and splits
it into two parts:
  - train.npz -> used once to build our model
  - job.npz   -> the data we will run inference on (this is what
                 later gets divided across two computers)
"""

import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

RANDOM_SEED = 42  #fixed number so the split is identical every time we run this

def main():
    digits = load_digits()
    X, y = digits.data, digits.target

    X_train, X_job, y_train, y_job = train_test_split(
        X, y, test_size=0.30, random_state=RANDOM_SEED, stratify=y
    )

    #simply organizing the data

    np.savez("train.npz", X=X_train, y=y_train) #contains the training images and their answers
    np.savez("job.npz", X=X_job, y=y_job) #contains the "job" images and their answers

    print(f"Train set: {X_train.shape[0]} samples -> train.npz")
    print(f"Job set:   {X_job.shape[0]} samples -> job.npz")

if __name__ == "__main__":
    main()