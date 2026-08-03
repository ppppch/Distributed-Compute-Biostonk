"""Phase 1 API for clinical-trial evidence retrieval."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from clinical.evidence_catalog import EvidenceCatalog
from clinical.trial_search import TrialSearch


class EvidenceSourceResponse(BaseModel):
    source_id: str
    source_type: str
    source_location: str
    content_hash_sha256: str
    source_modified_at: str


class ComparableTrialResponse(BaseModel):
    nct_id: str
    similarity: float
    sentiment: str
    source_workbook: str
    source: EvidenceSourceResponse


def create_app(
    dataset_path: Path = Path("clinical/data/trials.npz"),
    source_directory: Path = Path("clinical/data/Emde"),
) -> FastAPI:
    app = FastAPI(title="BioStonk Clinical Evidence API")
    catalog = EvidenceCatalog(source_directory)
    search = TrialSearch(dataset_path, catalog.source_records())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/trials/{nct_id}/comparables",
        response_model=list[ComparableTrialResponse],
    )
    def comparable_trials(
        nct_id: str,
        limit: int = Query(default=10, ge=1, le=100),
        source_workbook: str | None = None,
        sentiment: str | None = None,
    ) -> list[ComparableTrialResponse]:
        try:
            results = search.find_comparables(
                nct_id,
                limit=limit,
                source_workbook=source_workbook,
                sentiment=sentiment,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        return [
            ComparableTrialResponse(
                nct_id=result.nct_id,
                similarity=result.similarity,
                sentiment=result.sentiment,
                source_workbook=result.source_workbook,
                source=EvidenceSourceResponse(**result.source.__dict__),
            )
            for result in results
        ]

    return app


app = create_app()