"""Similarity retrieval over the imported clinical-trial embedding dataset."""

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np

from clinical.evidence_catalog import EvidenceSource
from clinical.metadata_catalog import TrialMetadataCatalog


@dataclass(frozen=True)
class ComparableTrial:
    """A retrieved trial with the provenance needed for review."""

    nct_id: str
    similarity: float
    sentiment: str
    source_workbook: str
    source: EvidenceSource
    metadata: dict | None


class TrialSearch:
    """Loads a validated trial dataset and returns cosine-similar records."""

    def __init__(
        self,
        dataset_path: Path,
        source_catalog: dict[str, EvidenceSource],
        metadata_catalog: TrialMetadataCatalog | None = None,
    ) -> None:
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
        self._source_catalog = source_catalog
        self._metadata_catalog = metadata_catalog
        self._indices_by_nct_id: dict[str, list[int]] = {}
        for index, nct_id in enumerate(self._nct_ids):
            self._indices_by_nct_id.setdefault(nct_id, []).append(index)
        self._anchor_index = self._build_anchor_index()

    def metadata_for(self, nct_id: str) -> dict | None:
        """Return imported structured metadata for a known Trial2Vec identifier."""
        return self._metadata_catalog.get(nct_id) if self._metadata_catalog else None

    def find_comparables(
        self,
        nct_id: str,
        limit: int = 10,
        source_workbook: str | None = None,
        sentiment: str | None = None,
        condition: str | None = None,
        phase: str | None = None,
        study_type: str | None = None,
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
            metadata = self._metadata_catalog.get(self._nct_ids[index]) if self._metadata_catalog else None
            if source_workbook and self._sources[index] != source_workbook:
                continue
            if sentiment and label != sentiment:
                continue
            if condition and not metadata_matches(metadata, "conditions", condition):
                continue
            if phase and not metadata_matches(metadata, "phases", phase):
                continue
            if study_type and not text_matches(metadata.get("study_type") if metadata else None, study_type):
                continue
            candidates.append(
                ComparableTrial(
                    nct_id=self._nct_ids[index],
                    similarity=float(similarities[index]),
                    sentiment=label,
                    source_workbook=self._sources[index],
                    source=self._source_catalog[self._sources[index]],
                    metadata=metadata,
                )
            )
            if len(candidates) == limit:
                break
        return candidates

    def _build_anchor_index(self) -> list[dict[str, object]]:
        """Return one deduplicated entry per known NCT ID, enriched when metadata exists."""
        seen: set[str] = set()
        anchors: list[dict[str, object]] = []
        for index, nct_id in enumerate(self._nct_ids):
            if nct_id in seen:
                continue
            seen.add(nct_id)
            metadata = self.metadata_for(nct_id)
            anchors.append(
                {
                    "nct_id": nct_id,
                    "source_workbook": self._sources[index],
                    "metadata": metadata,
                }
            )
        return anchors

    def anchor_trials(self, query: str | None = None, limit: int = 20) -> list[dict[str, object]]:
        """Return a curated, searchable list of anchor trials from the dataset."""
        if limit < 1:
            raise ValueError("limit must be at least 1")
        normalized_query = normalize(query) if query else ""
        results: list[dict[str, object]] = []
        for anchor in self._anchor_index:
            if normalized_query and not self._anchor_matches(anchor, normalized_query):
                continue
            results.append(anchor)
            if len(results) == limit:
                break
        return results

    def _anchor_matches(self, anchor: dict[str, object], normalized_query: str) -> bool:
        metadata = anchor["metadata"]
        if not isinstance(metadata, dict):
            metadata = None
        searchable: list[str | None] = [
            str(anchor["nct_id"]),
            metadata.get("official_title") if metadata else None,
            metadata.get("brief_summary") if metadata else None,
        ]
        if metadata:
            searchable.extend(metadata.get("conditions", []))
            searchable.extend(metadata.get("phases", []))
            searchable.append(metadata.get("study_type"))
            searchable.append(metadata.get("overall_status"))
        return any(normalized_query in normalize(value) for value in searchable if value)


def text_matches(value: str | None, expected: str) -> bool:
    return bool(value) and normalize(value) == normalize(expected)


def metadata_matches(metadata: dict | None, field: str, expected: str) -> bool:
    return bool(metadata) and any(text_matches(value, expected) for value in metadata.get(field, []))


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())