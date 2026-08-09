"""Deterministic Trial2Vec comparison workload shared by approved workers."""

import statistics
from typing import Any

from clinical.protocol_analysis import analyze_protocol_draft
from clinical.schemas import PredictionCandidate, ProtocolDraftAnalysisRequest
from clinical.trial_search import TrialSearch


def build_candidate_comparison(candidate: PredictionCandidate, search: TrialSearch) -> dict[str, Any]:
    """Compute one deterministic, JSON-serializable Trial2Vec comparison result."""
    comparables = search.find_comparables(candidate.anchor_nct_id, limit=5)
    trial_records = [
        {
            "nct_id": trial.nct_id,
            "similarity": round(trial.similarity, 4),
            "sentiment": trial.sentiment,
            "source_workbook": trial.source_workbook,
            "metadata": trial.metadata,
        }
        for trial in comparables
    ]
    anchor_metadata = search.metadata_for(candidate.anchor_nct_id)
    score_metadata = ([anchor_metadata] if anchor_metadata else []) + [
        trial["metadata"] for trial in trial_records if trial["metadata"]
    ]
    protocol_analysis = analyze_protocol_draft(ProtocolDraftAnalysisRequest(draft=candidate.draft))
    similarities = [trial["similarity"] for trial in trial_records]
    top_similarity = max(similarities, default=0)
    mean_similarity = statistics.fmean(similarities) if similarities else 0
    metadata_coverage = len(score_metadata) / (len(trial_records) + 1) if trial_records else 0
    coverage = protocol_analysis["coverage"]
    protocol_coverage = coverage["provided_design_field_count"] / coverage["required_design_field_count"]
    return {
        "candidate_id": candidate.candidate_id,
        "anchor_nct_id": candidate.anchor_nct_id,
        "analysis_type": "trial_similarity_comparison",
        "result_simulation": False,
        "top_match_similarity": round(top_similarity * 100, 1),
        "mean_match_similarity": round(mean_similarity * 100, 1),
        "comparison_label": "Top Trial2Vec cosine similarity to the selected anchor; not an outcome prediction",
        "measurements": [
            {"measurement": "Top neighbor similarity", "value": f"{top_similarity * 100:.1f}%", "source": "Trial2Vec cosine similarity"},
            {"measurement": "Mean neighbor similarity", "value": f"{mean_similarity * 100:.1f}%", "source": "Top retrieved Trial2Vec neighbors"},
            {"measurement": "Metadata coverage", "value": f"{metadata_coverage * 100:.1f}%", "source": "Local ClinicalTrials.gov catalog"},
            {"measurement": "Protocol field coverage", "value": f"{protocol_coverage * 100:.1f}%", "source": "Uploaded protocol fields"},
        ],
        "risk_indicators": risk_indicators(trial_records, protocol_analysis),
        "recommendations": recommendations(protocol_analysis, trial_records),
        "similar_historical_trials": trial_records,
        "protocol_coverage": coverage,
    }


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
    return indicators or ["No data-quality indicators were triggered."]


def recommendations(analysis: dict[str, Any], trials: list[dict[str, Any]]) -> list[str]:
    recommendations = [f"Add {field.replace('_', ' ')} to improve protocol coverage." for field in analysis["coverage"]["missing_design_fields"]]
    recommendations.extend(
        f"Add {field.replace('_', ' ')} to improve operational coverage."
        for field in analysis["coverage"]["missing_operational_fields"]
    )
    if len(trials) < 3:
        recommendations.append("Select an anchor with more Trial2Vec comparables before interpreting similarity.")
    return recommendations or ["Review retrieved historical trials with qualified clinical and operational reviewers."]