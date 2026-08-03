"""Local, immutable-after-finalization review ledger for Phase 1 briefs."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from clinical.claim_verifier import verify_claim
from clinical.evidence_brief import build_evidence_brief
from clinical.schemas import (
    ClaimReviewRequest,
    ClaimVerificationRequest,
    ReviewableBriefRequest,
)
from clinical.trial_search import TrialSearch


REVIEW_BRIEF_VERSION = "phase1-reviewable-brief-v1"


class ReviewLedger:
    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path

    def create_brief(self, request: ReviewableBriefRequest, search: TrialSearch) -> dict[str, Any]:
        claims = [self._verified_claim(request, claim, search) for claim in request.claims]
        if len({claim["claim_id"] for claim in claims}) != len(claims):
            raise ValueError("reviewable brief contains duplicate claim IDs")

        brief_id = stable_brief_id(request)
        payload = self._read()
        if brief_id not in payload["briefs"]:
            evidence_brief = build_evidence_brief(request.analysis_request, search)
            payload["briefs"][brief_id] = {
                "brief_id": brief_id,
                "brief_version": REVIEW_BRIEF_VERSION,
                "analysis_input_hash_sha256": request.analysis_request.input_hash(),
                "claims": claims,
                "limitations": evidence_brief["limitations"],
                "reviews": [],
                "status": "draft",
                "created_at": timestamp(),
                "finalized_at": None,
            }
            self._write(payload)
        return payload["briefs"][brief_id]

    def review_claim(
        self,
        brief_id: str,
        claim_id: str,
        request: ClaimReviewRequest,
    ) -> dict[str, Any]:
        payload = self._read()
        brief = self._brief(payload, brief_id)
        self._require_mutable(brief)
        if claim_id not in {claim["claim_id"] for claim in brief["claims"]}:
            raise KeyError(f"Unknown claim ID: {claim_id}")
        review = {
            "claim_id": claim_id,
            "reviewer_id": request.reviewer_id,
            "decision": request.decision,
            "note": request.note,
            "reviewed_at": timestamp(),
        }
        brief["reviews"].append(review)
        self._write(payload)
        return review

    def finalize_brief(self, brief_id: str) -> dict[str, Any]:
        payload = self._read()
        brief = self._brief(payload, brief_id)
        self._require_mutable(brief)
        latest_decisions = {
            review["claim_id"]: review["decision"] for review in brief["reviews"]
        }
        pending_claim_ids = [
            claim["claim_id"]
            for claim in brief["claims"]
            if latest_decisions.get(claim["claim_id"]) != "approved"
        ]
        if pending_claim_ids:
            raise ValueError(
                "all claims must have a latest approved review before finalization: "
                + ", ".join(pending_claim_ids)
            )
        brief["status"] = "finalized"
        brief["finalized_at"] = timestamp()
        self._write(payload)
        return brief

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        return self._brief(self._read(), brief_id)

    def export_markdown(self, brief_id: str) -> str:
        brief = self.get_brief(brief_id)
        lines = [
            "# BioStonk Reviewable Brief",
            "",
            f"- Brief ID: `{brief['brief_id']}`",
            f"- Version: `{brief['brief_version']}`",
            f"- Status: `{brief['status']}`",
            f"- Analysis input hash: `{brief['analysis_input_hash_sha256']}`",
            f"- Finalized at: {brief['finalized_at'] or 'Not finalized'}",
            "",
            "## Claims",
        ]
        for claim in brief["claims"]:
            reference = claim["reference"]
            lines.extend(
                [
                    f"### {claim['claim_id']}",
                    claim["claim_text"],
                    "",
                    f"- Type: `{claim['claim_type']}`",
                    f"- Verification: `{claim['verification_status']}`",
                    f"- Source ID: `{reference['source_id']}`",
                    f"- Source hash: `{reference['content_hash_sha256']}`",
                    f"- Field: `{reference['field_path']}`",
                    f"- Excerpt: {reference['excerpt']}",
                    "",
                ]
            )
            for review in (item for item in brief["reviews"] if item["claim_id"] == claim["claim_id"]):
                lines.append(
                    f"- Review: `{review['decision']}` by `{review['reviewer_id']}` at {review['reviewed_at']}"
                )
        lines.extend(["", "## Limitations", *[f"- {item}" for item in brief["limitations"]], ""])
        return "\n".join(lines)

    def _verified_claim(self, request: ReviewableBriefRequest, claim: Any, search: TrialSearch) -> dict[str, Any]:
        verification = verify_claim(
            ClaimVerificationRequest(
                analysis_request=request.analysis_request,
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                reference=claim.reference,
            ),
            search,
        )
        if verification["verification_status"] != "source_verified":
            raise ValueError(
                f"claim {claim.claim_id} is not source-verified: "
                + ", ".join(verification["rejection_reasons"])
            )
        return {
            "claim_id": claim.claim_id,
            "claim_text": claim.claim_text,
            "claim_type": claim.claim_type,
            "reference": claim.reference.model_dump(mode="json"),
            "verification_status": verification["verification_status"],
        }

    def _read(self) -> dict[str, Any]:
        if not self._store_path.exists():
            return {"briefs": {}}
        return json.loads(self._store_path.read_text())

    def _write(self, payload: dict[str, Any]) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._store_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        temporary_path.replace(self._store_path)

    @staticmethod
    def _brief(payload: dict[str, Any], brief_id: str) -> dict[str, Any]:
        if brief_id not in payload["briefs"]:
            raise KeyError(f"Unknown brief ID: {brief_id}")
        return payload["briefs"][brief_id]

    @staticmethod
    def _require_mutable(brief: dict[str, Any]) -> None:
        if brief["status"] == "finalized":
            raise RuntimeError("finalized briefs are immutable")


def stable_brief_id(request: ReviewableBriefRequest) -> str:
    payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()