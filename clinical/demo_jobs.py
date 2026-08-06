"""Simulated distributed Trial2Vec inference jobs for the product demo."""

from datetime import datetime, timezone
import statistics
from typing import Any
from uuid import uuid4

from clinical.protocol_analysis import analyze_protocol_draft
from clinical.schemas import ClinicalPredictionJobRequest, PredictionCandidate, ProtocolDraftAnalysisRequest
from clinical.trial_search import TrialSearch, normalize


LIFECYCLE = ("submitted", "sharded", "distributed", "running", "verified", "aggregated", "completed")
DEVICES = (
    {"device_id": "CRO-WS-014", "name": "Clinical Ops Workstation 14", "type": "Internal workstation", "cpu_cores": 16, "memory_gb": 64, "availability": "available", "approved": True},
    {"device_id": "PHARMA-DS-007", "name": "Translational Science Node 07", "type": "Internal workstation", "cpu_cores": 24, "memory_gb": 128, "availability": "available", "approved": True},
    {"device_id": "CRO-WS-021", "name": "Biometrics Workstation 21", "type": "Internal workstation", "cpu_cores": 12, "memory_gb": 32, "availability": "maintenance", "approved": True},
)
SCORE_VERSION = "phase1-experimental-demo-v1"


class DemoJobCoordinator:
    """Keeps demo job state in memory; no device execution or remote storage occurs."""

    def __init__(self, search: TrialSearch) -> None:
        self._search = search
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit(self, request: ClinicalPredictionJobRequest) -> dict[str, Any]:
        job_id = f"demo-{uuid4().hex[:12]}"
        assigned_devices = [device["device_id"] for device in DEVICES if device["availability"] == "available"]
        tasks = [
            {
                "task_id": f"{job_id}-candidate-{candidate.candidate_id}",
                "candidate_id": candidate.candidate_id,
                "device_id": assigned_devices[index % len(assigned_devices)],
                "status": "queued",
            }
            for index, candidate in enumerate(request.candidates)
        ]
        job = {
            "job_id": job_id,
            "status": LIFECYCLE[0],
            "lifecycle": list(LIFECYCLE),
            "created_at": timestamp(),
            "updated_at": timestamp(),
            "simulation": True,
            "execution_notice": "Device verification, sharding, and execution are simulated for this demo.",
            "tasks": tasks,
            "results": [self._candidate_result(candidate) for candidate in request.candidates],
        }
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> dict[str, Any]:
        if job_id not in self._jobs:
            raise KeyError(f"Unknown demo job ID: {job_id}")
        return self._jobs[job_id]

    def list_jobs(self) -> list[dict[str, Any]]:
        return sorted(self._jobs.values(), key=lambda job: job["created_at"], reverse=True)

    def advance(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        current_index = LIFECYCLE.index(job["status"])
        if current_index < len(LIFECYCLE) - 1:
            job["status"] = LIFECYCLE[current_index + 1]
            task_status = "running" if job["status"] == "running" else "completed" if job["status"] == "completed" else "queued"
            for task in job["tasks"]:
                task["status"] = task_status
            job["updated_at"] = timestamp()
        return job

    def devices(self) -> list[dict[str, Any]]:
        active_tasks = [task for job in self._jobs.values() if job["status"] != "completed" for task in job["tasks"]]
        return [
            {**device, "assigned_tasks": [task for task in active_tasks if task["device_id"] == device["device_id"]]}
            for device in DEVICES
        ]

    def _candidate_result(self, candidate: PredictionCandidate) -> dict[str, Any]:
        comparables = self._search.find_comparables(candidate.anchor_nct_id, limit=5)
        trial_records = [
            {
                "nct_id": trial.nct_id,
                "similarity": round(trial.similarity, 4),
                "source_workbook": trial.source_workbook,
                "metadata": trial.metadata,
            }
            for trial in comparables
        ]
        anchor_metadata = self._search.metadata_for(candidate.anchor_nct_id)
        score_metadata = ([anchor_metadata] if anchor_metadata else []) + [
            trial["metadata"] for trial in trial_records if trial["metadata"]
        ]
        protocol_analysis = analyze_protocol_draft(ProtocolDraftAnalysisRequest(draft=candidate.draft))
        score = experimental_score(candidate, trial_records, score_metadata, protocol_analysis)
        return {
            "candidate_id": candidate.candidate_id,
            "anchor_nct_id": candidate.anchor_nct_id,
            "experimental_demo_estimate": score,
            "score_label": "Experimental demo estimate (not a validated clinical prediction)",
            "factors": score_factors(candidate, trial_records, score_metadata, protocol_analysis),
            "risk_indicators": risk_indicators(trial_records, protocol_analysis),
            "recommendations": recommendations(protocol_analysis, trial_records),
            "similar_historical_trials": trial_records,
            "protocol_coverage": protocol_analysis["coverage"],
        }


def experimental_score(candidate: PredictionCandidate, trials: list[dict[str, Any]], metadata: list[dict[str, Any]], analysis: dict[str, Any]) -> int:
    factors = _factor_definitions(candidate, trials, metadata, analysis)
    total = sum(factor["contribution"] for factor in factors if factor["contribution"] is not None)
    return round(max(0, min(100, total)))


def score_factors(candidate: PredictionCandidate, trials: list[dict[str, Any]], metadata: list[dict[str, Any]], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    return _factor_definitions(candidate, trials, metadata, analysis)


def _factor_definitions(
    candidate: PredictionCandidate,
    trials: list[dict[str, Any]],
    metadata: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return one transparent factor record per scoring input.

    Each record contains the raw value, its weight, the points it contributes
    to the 0-100 experimental demo estimate, provenance, and availability.
    """
    similarities = [trial["similarity"] for trial in trials]
    required_design_fields = analysis["coverage"]["required_design_field_count"]
    provided_design_fields = analysis["coverage"]["provided_design_field_count"]
    design_coverage = provided_design_fields / required_design_fields if required_design_fields else 0

    definitions: list[dict[str, Any]] = [
        {
            "factor": "Trial2Vec similarity",
            "value": round(statistics.fmean(similarities), 3) if similarities else None,
            "weight": "50%",
            "source": "Trial2Vec embeddings",
            "source_type": "embedding",
            "availability": "available" if similarities else "unavailable",
        },
        {
            "factor": "Available historical completion status",
            "value": round(status_fraction(metadata, "COMPLETED"), 3),
            "weight": "15%",
            "source": "Imported ClinicalTrials.gov metadata",
            "source_type": "metadata",
            "availability": "available" if metadata else "unavailable",
        },
        {
            "factor": "Available phase alignment",
            "value": round(phase_fraction(metadata, candidate.draft.study_phase), 3),
            "weight": "10%",
            "source": "Imported ClinicalTrials.gov metadata",
            "source_type": "metadata",
            "availability": "available" if (metadata and candidate.draft.study_phase) else "unavailable",
        },
        {
            "factor": "Available enrollment alignment",
            "value": round(enrollment_alignment(metadata, candidate.draft.planned_enrollment), 3),
            "weight": "10%",
            "source": "Imported ClinicalTrials.gov metadata",
            "source_type": "metadata",
            "availability": "available" if (metadata and candidate.draft.planned_enrollment is not None) else "unavailable",
        },
        {
            "factor": "Available intervention-type alignment",
            "value": round(intervention_fraction(metadata, candidate.draft.intervention_type), 3),
            "weight": "10%",
            "source": "Imported ClinicalTrials.gov metadata",
            "source_type": "metadata",
            "availability": "available" if (metadata and candidate.draft.intervention_type) else "unavailable",
        },
        {
            "factor": "Protocol design coverage",
            "value": round(design_coverage, 3),
            "weight": "5%",
            "source": "Submitted protocol",
            "source_type": "protocol",
            "availability": "available" if required_design_fields else "unavailable",
        },
    ]

    for definition in definitions:
        definition["formula_version"] = SCORE_VERSION
        weight_decimal = float(definition["weight"].rstrip("%")) / 100
        definition["contribution"] = (
            round(definition["value"] * weight_decimal * 100, 2)
            if definition["value"] is not None
            else None
        )

    return definitions


def risk_indicators(trials: list[dict[str, Any]], analysis: dict[str, Any]) -> list[str]:
    indicators = []
    if analysis["coverage"]["missing_design_fields"]:
        indicators.append("Protocol design fields are incomplete.")
    if analysis["coverage"]["missing_operational_fields"]:
        indicators.append("Operational planning fields are incomplete.")
    if len(trials) < 3:
        indicators.append("Fewer than three Trial2Vec comparables were retrieved.")
    if any(trial["metadata"] is None for trial in trials):
        indicators.append("Some comparable trials lack imported structured metadata.")
    return indicators or ["No demo data-quality indicators were triggered."]


def recommendations(analysis: dict[str, Any], trials: list[dict[str, Any]]) -> list[str]:
    recommendations = [f"Add {field.replace('_', ' ')} to improve protocol coverage." for field in analysis["coverage"]["missing_design_fields"]]
    recommendations.extend(
        f"Add {field.replace('_', ' ')} to improve operational coverage."
        for field in analysis["coverage"]["missing_operational_fields"]
    )
    if len(trials) < 3:
        recommendations.append("Select an anchor with more Trial2Vec comparables before interpreting the demo estimate.")
    return recommendations or ["Review retrieved historical trials with qualified clinical and operational reviewers."]


def status_fraction(metadata: list[dict[str, Any]], expected: str) -> float:
    return fraction(metadata, lambda record: record.get("overall_status") == expected)


def phase_fraction(metadata: list[dict[str, Any]], phase: str | None) -> float:
    return fraction(metadata, lambda record: bool(phase) and any(normalize(item) == normalize(phase) for item in record.get("phases", [])))


def intervention_fraction(metadata: list[dict[str, Any]], intervention_type: str | None) -> float:
    return fraction(metadata, lambda record: bool(intervention_type) and any(normalize(item.get("type", "")) == normalize(intervention_type) for item in record.get("interventions", [])))


def enrollment_alignment(metadata: list[dict[str, Any]], enrollment: int | None) -> float:
    values = [record["enrollment"] for record in metadata if isinstance(record.get("enrollment"), int) and record["enrollment"] > 0]
    if enrollment is None or not values:
        return 0
    median = statistics.median(values)
    return max(0, 1 - abs(enrollment - median) / max(enrollment, median))


def fraction(values: list[dict[str, Any]], predicate: Any) -> float:
    return sum(bool(predicate(value)) for value in values) / len(values) if values else 0


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()