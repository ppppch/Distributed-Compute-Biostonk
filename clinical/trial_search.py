"""Similarity retrieval over the imported clinical-trial embedding dataset."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ComparableTrial:
    """A retrieved trial with the provenance needed for review."""

    nct_id: str
    similarity: float
    sentiment: str
    source_workbook: str


class TrialSearch:
    """Loads a validated trial dataset and returns cosine-similar records."""

    def __init__(self, dataset_path: Path) -> None:
        dataset = np.load(dataset_path)
        required_fields = {"nct_id", "X", "y", "label_names", "source_workbook"}
        missing_fields = required_fields - set(dataset.files)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Trial dataset is missing fields: {missing}")

        self._nct_ids = dataset["nct_id"].astype(str)
        self._embeddings = dataset["X"].astype(np.float32)
        self._sentiment_ids = dataset["y"].astype(np.int64)
        self._sentiment_names = dataset["label_names"].astype(str)
        self._sources = dataset["source_workbook"].astype(str)
        self._indices_by_nct_id: dict[str, list[int]] = {}
        for index, nct_id in enumerate(self._nct_ids):
            self._indices_by_nct_id.setdefault(nct_id, []).append(index)

    def find_comparables(
        self,
        nct_id: str,
        limit: int = 10,
        source_workbook: str | None = None,
        sentiment: str | None = None,
    ) -> list[ComparableTrial]:
        """Return records closest to the first matching NCT embedding."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if nct_id not in self._indices_by_nct_id:
            raise KeyError(f"Unknown NCT ID: {nct_id}")

        query_index = self._indices_by_nct_id[nct_id][0]
        query = self._embeddings[query_index]
        query_norm = np.linalg.norm(query)
        corpus_norms = np.linalg.norm(self._embeddings, axis=1)
        denominators = corpus_norms * query_norm
        similarities = np.divide(
            self._embeddings @ query,
            denominators,
            out=np.zeros_like(corpus_norms, dtype=np.float32),
            where=denominators != 0,
        )

        candidates: list[ComparableTrial] = []
        for index in np.argsort(-similarities):
            if index == query_index:
                continue
            label = self._sentiment_names[self._sentiment_ids[index]]
            if source_workbook and self._sources[index] != source_workbook:
                continue
            if sentiment and label != sentiment:
                continue
            candidates.append(
                ComparableTrial(
                    nct_id=self._nct_ids[index],
                    similarity=float(similarities[index]),
                    sentiment=label,
                    source_workbook=self._sources[index],
                )
            )
            if len(candidates) == limit:
                break
        return candidates