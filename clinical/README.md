# Clinical Trial Data

`import_trials.py` converts the tracked `data/Emde/` `.xlsx` workbooks containing `nct_id`, `emb_0` through
`emb_127`, and binary `sentiment` labels (`0.0` or `1.0`) into a compressed
`trials.npz` dataset. The generated dataset remains untracked.

Install the importer dependencies and run it against the attached data folder:

```bash
venv/bin/python -m pip install -r clinical/requirements.txt
venv/bin/python clinical/import_trials.py clinical/data/Emde
```

The output contains trial IDs, a `float32` embedding matrix (`X`), integer labels
(`y`), matching label names, and `source_workbook`. NCT IDs may occur in multiple
workbooks because each source is a separate annotation set; the importer retains
every valid source row. It rejects missing columns, incomplete embedding rows,
and malformed non-binary sentiment labels, reporting skipped rows for review.

## Similarity Retrieval

`trial_search.py` performs local cosine-similarity retrieval over the generated
dataset. It accepts a known `nct_id` and returns comparable trial records with
their sentiment label and source workbook. This is the initial evidence-retrieval
component; it does not yet claim clinical comparability beyond embedding
similarity.

Each returned trial includes a local evidence-source record: a stable source ID,
source type, source location, SHA-256 content hash, and source-file modified
timestamp.
The supplied workbooks do not include public source URLs or licensing metadata,
so those fields must be added from an approved evidence registry before making
external regulatory claims.

## Program Profile Contract

`POST /analysis-requests/validate` accepts the canonical program profile and
evidence scope, then returns a deterministic input hash. This records the exact
analysis input without performing retrieval or storing data remotely. The current
Emde corpus does not contain structured endpoint, phase, population, or
jurisdiction metadata, so those fields are validated for future evidence sources
but cannot yet be used as retrieval filters.

## Trial Metadata Catalog

`import_metadata.py` converts an approved ClinicalTrials.gov API v2 JSON export
into an NCT-keyed local metadata catalog. The generated `trial_metadata.json`
stays ignored because it is a refreshed data artifact.

```bash
venv/bin/python clinical/import_metadata.py path/to/clinicaltrials-studies.json
```

The importer preserves null or empty values when source fields are absent and
adds a source URL, retrieval timestamp, and content hash to every record.

To prepare a bounded 25-study demo export from the local embedding dataset, run:

```bash
venv/bin/python clinical/fetch_metadata.py --limit 25
venv/bin/python clinical/import_metadata.py clinical/data/studies.json
```

`fetch_metadata.py` calls the official ClinicalTrials.gov v2 API once per NCT
ID and defaults to a 0.1-second delay between calls. Keep demo cohorts at 100
studies or fewer unless the project lead approves a larger refresh.

When `trial_metadata.json` is present, comparable-trial retrieval includes the
matching verified metadata and supports `condition`, `phase`, and `study_type`
query filters using normalized exact matching. Responses explicitly mark
metadata coverage with `metadata_available`; trials without matching catalog
data are excluded from filtered results rather than having metadata inferred.

Run the API after generating `trials.npz`:

```bash
venv/bin/uvicorn clinical.api:app --reload
```

For example, `GET /trials/NCT05071248/comparables?limit=10` returns the nearest
stored trial embeddings along with their source provenance.

## Protocol Draft Analysis

`POST /protocol-drafts/analyze` is the local API contract for a debounced
protocol editor. Submit the current draft and, after an edit, the preceding
draft. The response provides deterministic draft hashes, missing design and
operational fields, and a field-level change list. It explicitly returns
`prediction.available: false`: the current sentiment-labeled embeddings cannot
support a calibrated trial probability-of-success model.

## Local Trial Comparison

The workspace at `/` is a local CRO/pharma demonstration. Users paste or upload
a protocol, choose a known Trial2Vec NCT ID as the retrieval anchor, and submit
one or two candidates for comparison. The selected anchor is required because
this repository has Trial2Vec embeddings for historical trials but no protocol
text embedding model.

`POST /comparison-jobs` creates two replicas per candidate. Distinct approved
workers pull replicas, execute them against matching local Trial2Vec artifacts,
and submit canonical result hashes:

```text
queued -> running -> verifying -> aggregated -> completed
```

`GET /comparison-jobs/{job_id}` polls worker-driven state and
`GET /comparison-jobs/history` lists active and completed comparisons.
Workers register at `POST /compute/workers/register`, pull from
`POST /compute/workers/{worker_id}/next-task`, and submit to
`POST /compute/workers/{worker_id}/results`. Aggregation occurs only when replica
payload hashes agree and the replicas were processed by distinct workers.

Run the coordinator and two local worker processes in separate terminals:

```bash
make clinical-server
make clinical-worker-a
make clinical-worker-b
```

For a two-laptop pilot, follow [the LAN runbook](../TWO_LAPTOP_PILOT.md). Strict
mode requires `BIOSTONK_REQUIRE_DISTINCT_HOSTS=true` and blocks work until two
allowlisted workers on distinct hostnames report the same full artifact bundle
checksum. This is process allowlisting, not production hardware identity.

Each completed result includes real Trial2Vec nearest-neighbor retrieval,
`top_match_similarity`, `mean_match_similarity`, metadata coverage, and protocol
field coverage. Similarity values are direct cosine measurements against the
selected known anchor. They are not probabilities of success, validated clinical
predictions, clinical advice, operational advice, or regulatory advice. Uploaded
protocol content remains in coordinator/worker memory only and is not used for
online training.

## Local Evidence Brief

`POST /analysis-requests/brief` produces a deterministic JSON evidence brief
from a validated program profile, the selected anchor trial, local retrieval
results, source provenance, and available metadata. It reports metadata coverage
and limitations explicitly; it does not generate clinical or regulatory claims.

## Claim Source Verification

`POST /claims/verify` verifies a user-supplied claim reference against the
retrieved metadata for the supplied analysis request. The reference must provide
the retrieved NCT ID, source ID, content hash, JSON-pointer field path, and a
verbatim excerpt. A `source_verified` result confirms only that provenance and
excerpt match; it does not establish clinical or regulatory validity of the
claim.

## Local Review Ledger

`POST /reviewable-briefs` creates a local draft only when every submitted claim
is source-verified. Review one claim at a time with
`POST /reviewable-briefs/{brief_id}/claims/{claim_id}/reviews`, then finalize
only when every claim's latest review is approved:

```text
POST /reviewable-briefs/{brief_id}/finalize
GET /reviewable-briefs/{brief_id}/export.md
```

Finalized briefs are immutable. The local JSON ledger defaults to
`clinical/data/reviewed_briefs.json`, which remains ignored by Git. This is a
Phase 1 demo ledger, not an enterprise identity, authorization, or audit system.

## Evidence Quality Evaluation

`evaluate_claims.py` scores a reviewer-authored JSON file of source-reference
examples. Each example includes an expected verifier result plus a qualified
reviewer's source-support and applicability labels. It reports source-reference
precision and recall, verifier mismatches, and reviewer-labeled evidence gaps:

```bash
venv/bin/python -m clinical.evaluate_claims path/to/evaluation.json
```

The evaluator does not create labels or judge clinical or regulatory validity.
Do not treat an evaluation run as qualified review unless the input set was
assembled and labeled by approved domain reviewers.

## Reviewer Packet

`review_packet.py` creates a bounded JSON packet of retrieved metadata excerpts
for qualified reviewers. It preserves each candidate's source ID, URL, content
hash, and JSON-pointer field path, but never creates claims or review labels:

```bash
venv/bin/python -m clinical.review_packet request.json --output reviewer-packet.json
```

Reviewers use this packet to create source-backed evaluation examples, then add
their own support and applicability labels before running `evaluate_claims.py`.