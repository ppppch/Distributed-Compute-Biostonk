"""Local provenance catalog for approved clinical evidence sources."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path


@dataclass(frozen=True)
class EvidenceSource:
    """Immutable provenance details for one source workbook."""

    source_id: str
    source_type: str
    source_location: str
    content_hash_sha256: str
    source_modified_at: str


class EvidenceCatalog:
    """Builds an in-memory provenance catalog from approved local files."""

    def __init__(self, source_directory: Path) -> None:
        self._sources = {
            path.name: self._create_source(path)
            for path in source_directory.glob("*.xlsx")
        }

    def get_source(self, workbook_name: str) -> EvidenceSource:
        try:
            return self._sources[workbook_name]
        except KeyError as error:
            raise KeyError(f"Unknown evidence source: {workbook_name}") from error

    def source_records(self) -> dict[str, EvidenceSource]:
        return self._sources.copy()

    @staticmethod
    def _create_source(path: Path) -> EvidenceSource:
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        source_modified_at = datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.utc
        ).isoformat()
        return EvidenceSource(
            source_id=f"emde:{content_hash[:16]}",
            source_type="clinical_trial_embedding_workbook",
            source_location=f"clinical/data/Emde/{path.name}",
            content_hash_sha256=content_hash,
            source_modified_at=source_modified_at,
        )