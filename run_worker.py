"""
Worker step: run inference on a single chunk of job data.

This replaces the duplicated run_worker1.py / run_worker2.py scripts.
In a real distributed system each worker would be an identical process
running on a different machine with its own input chunk.
"""

import argparse
import numpy as np
import joblib


DEFAULT_MODEL_PATH = "baseline_model.joblib"


def run_worker(input_path: str, output_path: str, model_path: str = DEFAULT_MODEL_PATH) -> int:
    """
    Load a trained model and run inference on one chunk of job data.

    Args:
        input_path: Path to the input .npz chunk (must contain 'X' and 'original_index').
        output_path: Path where predictions will be saved.
        model_path: Path to the trained model file.

    Returns:
        Number of samples processed.
    """
    model = joblib.load(model_path)
    data = np.load(input_path)
    X_part = data["X"]
    original_index = data["original_index"]

    predictions = model.predict(X_part)

    np.savez(output_path, predictions=predictions, original_index=original_index)
    return X_part.shape[0]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Run distributed inference on one chunk of job data."
    )
    parser.add_argument("input", help="Path to input .npz chunk")
    parser.add_argument("output", help="Path to output .npz results")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_PATH,
        help="Path to trained model file (default: baseline_model.joblib)",
    )
    parser.add_argument(
        "--label",
        default="Worker",
        help="Label to print in status message",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    n_samples = run_worker(args.input, args.output, args.model)
    print(f"Processed {n_samples} samples ({args.label})")


if __name__ == "__main__":
    main()
