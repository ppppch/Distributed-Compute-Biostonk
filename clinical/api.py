"""Phase 1 API for clinical-trial evidence retrieval."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from clinical.trial_search import TrialSearch


class ComparableTrialResponse(BaseModel):
    nct_id: str
    similarity: float
    sentiment: str
    source_workbook: str


def create_app(dataset_path: Path = Path("clinical/data/trials.npz")) -> FastAPI:
    app = FastAPI(title="BioStonk Clinical Evidence API")
    search = TrialSearch(dataset_path)

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

        return [ComparableTrialResponse(**result.__dict__) for result in results]

    return app


app = create_app()