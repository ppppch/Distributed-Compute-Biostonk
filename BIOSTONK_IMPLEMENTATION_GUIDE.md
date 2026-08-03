# BioStonk Product Requirements

## Read This First

This document is the working guide for BioStonk interns. Start with **Current
State** and **Next Assigned Deliverable** before changing code.

BioStonk is not yet a clinical decision-support product. The repository has a
working clinical-trial embedding retrieval prototype and a separate distributed
MNIST demonstration. Do not describe embedding similarity as regulatory
comparability, and do not present generated output as clinical or regulatory
advice.

### Current State

| Capability | Status | Location |
|---|---|---|
| Imported clinical embeddings | Complete | `clinical/data/Emde/` |
| Local trial similarity search | Complete | `clinical/trial_search.py` |
| Evidence-source hash and provenance | Complete | `clinical/evidence_catalog.py` |
| Program-profile schema and input fingerprint | Complete | `clinical/schemas.py` |
| Clinical evidence API | Complete | `clinical/api.py` |
| Structured trial metadata | Not started | Required before metadata filters |
| Source-linked regulatory claims | Not started | Phase 2 |
| Web app, authentication, tenant isolation | Not started | Phase 3 |
| Distributed clinical task execution | Not started | Phase 4 |

### Run Locally

```bash
venv/bin/python -m pip install -r clinical/requirements.txt
venv/bin/python clinical/import_trials.py clinical/data/Emde
venv/bin/python -m unittest discover -s tests -v
venv/bin/uvicorn clinical.api:app --reload
```

The clinical API is local and does not use Firebase.

## Product Vision

BioStonk is an enterprise clinical AI platform that turns fragmented clinical
and regulatory evidence into an auditable decision-support brief. Its first
workflow supports regulatory precedent analysis for orphan-drug and rare-disease
programs.

The product helps teams identify comparable programs, endpoint and trial-design
precedents, relevant patient populations and control designs, evidence gaps,
potential regulatory risks, and the sources supporting every conclusion.

## Target Users

Primary user:

- Regulatory strategists and regulatory-intelligence professionals at biotech
  and pharmaceutical companies.

Economic buyers:

- Head or VP of Regulatory Affairs
- Head of Clinical Development
- Chief Medical Officer
- Head of Regulatory Intelligence

Technical approvers:

- IT, security, privacy, and data teams

## Problem Statement

Regulatory evidence is dispersed across trial registries, regulatory documents,
scientific literature, natural-history studies, and approved internal material.
Teams need to determine what programs are truly comparable, what endpoints have
precedent, what evidence supported prior decisions, and where a proposed trial
strategy may receive scrutiny.

Current processes are slow, difficult to defend, and repeatedly rebuilt as trial
designs or available evidence change. BioStonk must produce a source-linked,
repeatable, and auditable precedent map rather than an unsupported AI summary.

## First Workflow

### Input

- Program profile: indication, disease subtype, modality, sponsor assumptions,
  proposed population, intervention, comparator, endpoints, and trial phase.
- Approved evidence sources: clinical-trial records, public regulatory material,
  scientific literature, natural-history studies, and customer-approved internal
  documents.
- User-selected filters: jurisdiction, date range, regulatory agency, and
  evidence types.

### Output

An auditable decision-support brief containing:

- Comparable development programs with similarity rationale.
- Endpoint, population, comparator, and trial-design precedent.
- Evidence gaps, uncertainty, and potential regulatory risks.
- Claim-level citations, quotations or source excerpts, and source metadata.
- A reproducible analysis record showing inputs, model/version, task results,
  and verification status.

## Product Requirements

### Evidence Ingestion

- Import public clinical-trial records and the existing clinical embedding data.
- Support controlled upload of customer-approved documents.
- Preserve source provenance, licensing status, ingestion timestamp, document
  version, and content hash.
- Extract structured fields where possible and retain the original source for
  citation.

### Retrieval and Comparison

- Index evidence by disease, indication, modality, endpoint, population,
  comparator, phase, and jurisdiction.
- Retrieve candidate comparable programs using structured filters and embedding
  similarity.
- Present a human-reviewable rationale for each comparison.
- Keep retrieval results and their source versions with each analysis run.

### Analysis and Brief Generation

- Break analysis into bounded tasks such as trial matching, endpoint precedent,
  population precedent, and risk/evidence-gap review.
- Require every generated claim to reference one or more retrieved sources.
- Clearly label unsupported, conflicting, or low-confidence findings.
- Produce an exportable brief and a structured JSON representation.

### Audit and Review

- Record the user, input profile version, source set, prompt/template version,
  model version, task result, verifier result, and final brief version.
- Let users inspect every claim and navigate to its supporting sources.
- Support reviewer comments, approval state, and immutable finalization of a
  released brief.

### Security and Tenant Isolation

- Enforce organization and project-level access control.
- Keep customer uploads isolated by tenant; no cross-customer retrieval.
- Encrypt data in transit and at rest; store secrets outside source control.
- Log access to customer documents and analysis results.
- Do not use protected health information in the MVP without a defined privacy,
  security, and contractual review.

## Next Assigned Deliverable

### Clinical-Trial Metadata Catalog

The immediate blocker is missing structured metadata. The Emde files provide
only `nct_id`, 128 embedding values, source workbook, and a binary sentiment
label. They do **not** provide disease, endpoint, phase, population, comparator,
or jurisdiction. Do not build filters for fields that are not in an approved
source.

Build a local metadata catalog keyed by `nct_id` using an approved clinical-trial
source or a provided export. The catalog must support these fields when available:

- Official title and brief summary
- Conditions and disease subtype
- Study phase and study type
- Intervention, comparator, and arm description
- Primary and secondary outcomes
- Eligibility/population information
- Sponsor, status, dates, and jurisdictions/locations
- Original source URL, retrieval timestamp, license or use status, and content
  hash

#### Definition of Done

- A reproducible importer produces a local, ignored metadata artifact.
- Every metadata record has an `nct_id`, `source_id`, source URL, retrieval time,
  and SHA-256 content hash.
- Missing fields remain `null` or empty; do not infer clinical facts.
- The API can filter results by at least condition, phase, and study type when
  those fields are present.
- Tests cover import validation, an NCT ID with metadata, an NCT ID without
  metadata, and each supported filter.
- Documentation identifies the source, refresh procedure, and any license or
  use restrictions.

## Engineering Rules

- Keep raw approved source files and generated artifacts separate. Commit only
  source files that the project is allowed to distribute.
- Preserve source provenance and content hashes. Never replace a source record
  silently.
- Every new endpoint needs a focused test and must keep the full test suite
  passing.
- Never commit credentials, API keys, service-account files, PHI, or customer
  documents.
- Do not add generative claim production until claim-level source verification is
  implemented.
- Prefer local files and local computation during Phase 1.

### Firebase Rules

Firebase is not needed for the current clinical retrieval work. The existing
Firestore audit is optional and write-only when enabled. Keep it free of
collection queries, listeners, polling, and document reads.

Before enabling or adding Firebase-backed functionality, notify the project lead
to check Firebase usage. The intended budget is below 50,000 Firestore reads per
day. Any proposed Firebase feature must document its expected reads per user
action and per day before implementation.

## Distributed Compute Requirements

Distributed compute is an implementation mechanism, not the primary customer
value. It must process independent analysis tasks across customer-approved
hardware while preserving verification and auditability.

- A coordinator creates a task manifest with task ID, input hash, required model
  version, allowed data scope, and expected output schema.
- Workers receive only the minimum authorized data for their task.
- Workers return a result, source references, task-input hash, output hash, and
  runtime metadata.
- A verifier checks schema validity, source references, task completeness, and
  deterministic hashes before aggregation.
- The coordinator retries failed tasks and marks irrecoverable tasks explicitly;
  it must not silently omit evidence.
- The existing server/client prototype provides a starting pattern for splitting,
  processing, combining, and verifying work, but it does not yet satisfy these
  clinical or enterprise requirements.

## Delivery Plan

### Phase 1: Evidence Foundation

- Complete the clinical-trial metadata catalog described above.
- Extend retrieval with approved structured metadata filters.
- Define analysis-task, claim, and brief schemas after the metadata contract is
  stable.

### Phase 2: Auditable Analysis

- Implement the first analysis tasks: comparable-program discovery and endpoint
  precedent extraction.
- Create a source-linked claim format and verifier.
- Generate a reviewable brief from a fixed evidence set.
- Evaluate citation precision and reviewer acceptance with domain experts.

### Phase 3: Enterprise Workflow

- Build authentication, organizations, projects, roles, and document access
  controls.
- Add customer document ingestion and approved-source controls.
- Create the regulatory strategist workspace and export workflow.
- Complete security, privacy, retention, and audit requirements with customer
  IT teams.

### Phase 4: Distributed Enterprise Execution

- Implement approved-worker enrollment, task manifests, least-privilege data
  delivery, verification, failure recovery, and observability.
- Benchmark throughput, correctness, and cost against centralized execution.
- Roll out only after the centralized workflow is auditable and useful.

## Success Criteria

- A regulatory professional can create a program profile and receive a brief
  with inspectable source support for every material conclusion.
- Reviewers can reproduce an analysis from its recorded inputs and source
  versions.
- The system flags missing, conflicting, or insufficient evidence rather than
  presenting unsupported certainty.
- Customer data remains tenant-isolated and access-audited.
- Distributed execution produces the same verified task outputs as an approved
  baseline execution.