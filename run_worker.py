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

def initialize_firebase():
    """Initialize Firebase Admin SDK if available and not already initialized."""
    if firebase_admin is None:
        raise ImportError("firebase-admin package is not installed. Run 'pip install firebase-admin'.")
    
    if not firebase_admin._apps:
        # Uses standard google app environment variable or default credentials
        firebase_admin.initialize_app()
    
    return firestore.client()

def fetch_chunk_assignment(job_id: str, chunk_id: str) -> dict:
    """
    Fetch worker task assignment from Firestore while strictly respecting read limits.
    
    Target: Consumes ~2 Firestore reads total (1 job doc, 1 chunk doc).
    """
    db = initialize_firebase()
    
    # Read 1: Check overall job metadata
    job_ref = db.collection("jobs").document(job_id)
    job_doc = job_ref.get()
    
    if not job_doc.exists:
        raise ValueError(f"Job '{job_id}' not found in Firestore.")

    # Read 2: Fetch specific chunk metadata
    chunk_ref = db.collection("jobs").document(job_id).collection("chunks").document(chunk_id)
    chunk_doc = chunk_ref.get()
    
    if not chunk_doc.exists:
        raise ValueError(f"Chunk '{chunk_id}' not found under Job '{job_id}'.")

    chunk_data = chunk_doc.to_dict()
    print(f"[Firestore Log] Read assignment for Job '{job_id}', Chunk '{chunk_id}'.")
    return chunk_data

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

    input_path = args.input
    output_path = args.output

    # If Firestore coordination arguments are supplied, fetch file paths from metadata
    if args.job_id and args.chunk_id:
        print(f"Fetching task assignment for Job: {args.job_id}, Chunk: {args.chunk_id}...")
        chunk_metadata = fetch_chunk_assignment(args.job_id, args.chunk_id)
        
        # Override file paths from compact Firestore metadata if not given explicitly
        if not input_path:
            input_path = chunk_metadata.get("inputArtifact")
        if not output_path:
            output_path = chunk_metadata.get("outputArtifact")

    if not input_path or not output_path:
        raise ValueError("Missing required file paths. Provide positional arguments input/output or --job-id/--chunk-id.")
    
    n_samples = run_worker(args.input, args.output, args.model)
    print(f"Processed {n_samples} samples ({args.label})")


if __name__ == "__main__":
    main()
