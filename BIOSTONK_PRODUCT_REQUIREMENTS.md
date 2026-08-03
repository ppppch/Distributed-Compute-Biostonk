# BioStonk Product Requirements

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

## MVP Requirements

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

## Current Repository Gap

The repository currently provides a distributed inference prototype, FastAPI
server/client communication, a Firestore metadata audit option, and a clinical
embedding importer. It does not yet provide the BioStonk product workflow.

Required implementation work:

1. Replace the MNIST-specific model and request schema with clinical evidence
   task schemas.
2. Build an evidence catalog with provenance, document storage, metadata, and
   searchable embeddings.
3. Add a clinical-trial similarity and filtering service using the imported
   `nct_id` embedding data.
4. Build a task coordinator, worker registration, retry policy, and verifier for
   source-linked analysis tasks.
5. Add a web application for program setup, evidence review, claim-level
   citations, brief review, and export.
6. Add authentication, tenant isolation, role-based access control, and security
   logging before accepting customer documents.
7. Replace the current optional Firestore job audit with a production audit
   design that records analysis lineage without storing sensitive document
   content unnecessarily.
8. Add evaluation datasets and human-review criteria for comparability,
   citation accuracy, and regulatory usefulness.

## Delivery Plan

### Phase 1: Evidence Foundation

- Define the canonical program-profile, evidence-source, analysis-task, claim,
  and brief schemas.
- Import and validate clinical-trial embeddings from `clinical/data/Emde/`.
- Build trial filtering and similarity retrieval with test fixtures.
- Establish provenance and content-hash storage for every source.

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