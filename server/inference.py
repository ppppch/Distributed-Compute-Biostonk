"""Deterministic model and dataset utilities for the LAN inference demo."""

from dataclasses import dataclass
import hashlib
import time
from typing import Any

import numpy as np
from sklearn.datasets import load_digits
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

RANDOM_SEED = 42
MODEL_VERSION = "digits-rf-v1-seed42-trees100"


@dataclass(frozen=True)
class DemoAssets:
    """Frozen model inputs and single-machine baseline for one coordinator."""

    model: Any
    inputs: np.ndarray
    labels: np.ndarray
    baseline_predictions: np.ndarray
    baseline_checksum: str
    baseline_processing_seconds: float
    model_version: str = MODEL_VERSION


def prediction_checksum(predictions: list[int] | np.ndarray) -> str:
    """Return a stable checksum for integer predictions."""

    values = np.asarray(predictions, dtype=np.int64)
    return hashlib.sha256(values.tobytes()).hexdigest()


def build_demo_assets(sample_count: int | None = None) -> DemoAssets:
    """Train the fixed digits model and compute its baseline predictions."""

    digits = load_digits()
    train_inputs, job_inputs, train_labels, job_labels = train_test_split(
        digits.data,
        digits.target,
        test_size=0.30,
        random_state=RANDOM_SEED,
        stratify=digits.target,
    )
    if sample_count is not None:
        if sample_count < 2 or sample_count > len(job_inputs):
            raise ValueError(f"sample_count must be between 2 and {len(job_inputs)}")
        job_inputs = job_inputs[:sample_count]
        job_labels = job_labels[:sample_count]

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(train_inputs, train_labels)

    started_at = time.perf_counter()
    baseline_predictions = np.asarray(model.predict(job_inputs), dtype=np.int64)
    elapsed = time.perf_counter() - started_at
    return DemoAssets(
        model=model,
        inputs=np.asarray(job_inputs, dtype=np.float64),
        labels=np.asarray(job_labels, dtype=np.int64),
        baseline_predictions=baseline_predictions,
        baseline_checksum=prediction_checksum(baseline_predictions),
        baseline_processing_seconds=elapsed,
    )
