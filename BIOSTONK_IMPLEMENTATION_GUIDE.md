# BioStonk One-Week Demo Implementation Guide

## Read This First

This document is the working guide for the project lead and interns Ryan and
Maggie for the August 3-7, 2026 demo sprint. Start with **Sprint Goal**,
**Contribution Model**, and **Today** before changing code. The product
requirements below remain the long-term reference, but the one-week plan
controls this sprint.

**Mission this week:** improve the local web application at
`http://127.0.0.1:8001`, make its complete demo workflow reliable and clear,
and use what we learn to decide the next steps. This is not an agenda for the
rest of the internship. The long-term sections are product context, not assigned
intern tracks.

BioStonk is not yet a clinical decision-support product. The repository has a
working Trial2Vec retrieval workflow, an experimental demo estimate, a simulated
distributed job lifecycle, and a separate distributed MNIST demonstration. Do
not describe the demo estimate as a probability of success or present generated
output as clinical, operational, or regulatory advice.

## Sprint Goal

By Friday, August 7, a CRO or pharmaceutical user can complete this demo without
developer intervention:

1. Open the BioStonk workspace and paste or upload a protocol draft.
2. Select a known Trial2Vec anchor trial from a usable catalog instead of typing
   an unknown NCT ID from memory.
3. Submit one protocol or compare two protocol candidates.
4. Watch the simulated workflow move through submitted, sharded, distributed,
   running, verified, aggregated, and completed states.
5. Inspect the experimental demo estimate, factor calculation, data-coverage
   warnings, and real Trial2Vec nearest neighbors.
6. Inspect approved mock devices, capacity, assigned tasks, and job history.
7. Repeat the scripted demo from a clean checkout using documented commands.

The week is successful when the complete scripted workflow is stable,
understandable, source-aware, and honest about what is real and what is mocked.
It is not successful merely because more backend capabilities exist.

## One-Week Scope Lock

### Must Ship

- A polished local browser workflow for paste and `.txt`/`.md` upload.
- Searchable curated Trial2Vec anchors and five real nearest neighbors per result.
- One-candidate and two-candidate comparison workflows.
- A versioned, transparent experimental estimate with factor availability and
  metadata coverage.
- Simulated lifecycle, approved devices, task assignments, verification, and
  job history.
- A visibly simulated compute-cost summary with documented assumptions so the
  predictable-cost story can be demonstrated without making a savings claim.
- Clean setup instructions, browser smoke checklist, demo scripts, screenshots,
  and a backup recording.

### Explicitly Out of Scope This Week

- A validated probability-of-success model or model training on sentiment labels.
- Embedding arbitrary uploaded protocol text with Trial2Vec.
- PDF or DOCX extraction; convert those files to text before the demo.
- Real endpoint enrollment, remote code execution, sharding, verification, or
  hardware telemetry.
- Authentication, organizations, tenant isolation, customer document storage,
  cloud deployment, billing, or production security claims.
- Firebase integration or persistence.
- Generative clinical, operational, or regulatory recommendations.

If a requested feature is outside this scope, record it in the post-demo backlog
instead of implementing it during the sprint.

## Contribution Model

### Project Lead

Compile the work, select the strongest implementation, and make final integration
decisions when contributions overlap.

- Freeze the score formula, labels, demo anchors, and demo script.
- Review candidate contributions at least twice daily.
- Keep the main branch runnable and the full test suite passing.
- Run the daily integration demo and maintain the blocker list.
- Approve all language describing prediction, validation, cost, or security.
- Prepare the final customer narrative and backup recording.

### Intern Contributions

Both interns may contribute to any part of the demo. Roles are not assigned in
advance. Each intern should choose a concrete issue, state which files they plan
to edit, and submit a small self-contained implementation for review.

- Independent solutions to the same problem are allowed when they explore
  meaningfully different approaches.
- Do not assume an intern contribution will be merged unchanged. The project
  lead may select one version, combine the strongest parts, or reject both.
- Include focused tests, screenshots for visual work, and a short explanation of
  tradeoffs so contributions can be compared fairly.
- Preserve current API behavior unless the contribution explicitly documents a
  coordinated contract change.
- Avoid large refactors that make useful pieces difficult to extract.

### Contribution Backlog

Interns may select from any unclaimed item below:

- Build clearer workspace, jobs, results/comparison, or devices views.
- Add loading, empty, error, invalid-NCT, and missing-metadata states.
- Improve protocol upload, candidate comparison, and result navigation.
- Add an anchor-trial catalog/search endpoint for the UI.
- Enrich the curated demo anchors and their nearest neighbors with approved
  ClinicalTrials.gov metadata.
- Version and test the experimental score formula and data-coverage behavior.
- Make job history and lifecycle transitions deterministic and recoverable for
  the local demo.
- Add focused tests for invalid anchors, sparse metadata, two candidates, and
  lifecycle edge cases.
- Add deterministic task manifests, hashes, verification details, or simulated
  cost assumptions.
- Verify desktop and mobile layouts and improve the browser smoke checklist.

Before starting, write the selected item and planned files in the team channel.
If both interns need the same file, coordinate the intended changes or work in
separate copies so the project lead can compare them. Prefer small patches that
can be selectively applied over long-lived personal branches.

## Today: Monday, August 3

The current uncommitted demo baseline must be stabilized before parallel work.

### Project Lead

- [ ] Review the current diff and commit the validated Trial2Vec demo baseline.
- [ ] Share the validated baseline commit with both interns.
- [ ] Ask each intern to claim one concrete backlog item and list planned files.
- [ ] Confirm these commands work from the repository root:

  ```bash
  venv/bin/python -m unittest discover -s tests -v
  venv/bin/python -m uvicorn clinical.api:app --host 127.0.0.1 --port 8001
  ```

- [ ] Freeze three curated demo anchors and record why each is useful.
- [ ] Run a 10-minute kickoff covering the prediction boundary and contribution
  process.

### Intern Contributions

- [ ] Both interns walk through `http://127.0.0.1:8001` independently.
- [ ] Each intern proposes a ranked list of three improvements with expected
  user impact, implementation cost, and risk.
- [ ] Each intern selects one approved improvement and submits a small candidate
  implementation with tests or screenshots.
- [ ] At least one contribution addresses user experience and at least one
  addresses data, scoring, or job reliability. Either intern may do either.

### Monday Exit Criteria

- The baseline commit is shared with both interns.
- The full suite passes on all three machines.
- Three demo anchors are agreed upon.
- Both interns have submitted one reviewable candidate contribution.
- Anchor listing and metadata coverage are both claimed as concrete candidate
  contributions for the next day, chosen after reviewing Monday's work.
- No Firebase work is started.

## Week Schedule

### Tuesday, August 4: Complete the Core Workflow

**Candidate contribution pool**

- Finish protocol paste/upload, anchor selection, one-candidate submission, and
  clear lifecycle animation.
- Add accessible loading, disabled, error, and empty states.
- Keep layout stable on 1440 px desktop and 390 px mobile viewports.
- Complete anchor search and curated metadata enrichment.
- Make scoring deterministic and return formula version, factor contribution,
  source type, and availability for each factor.
- Test submitted-through-completed lifecycle progression and unknown job IDs.

Each intern selects one or more approved items. They may work on different items
or submit competing approaches to the same item. The project lead selects and
combines the strongest work at the integration checkpoint.

**Project Lead integration checkpoint at 4:00 PM**

- Run one clean one-candidate workflow.
- Reject any UI or API wording that calls the estimate a probability.
- Merge only when focused tests and the full suite pass.

### Wednesday, August 5: Comparison and Compute Story

**Candidate contribution pool**

- Finish two-candidate comparison with visible field and score-factor deltas.
- Finish jobs history and device-management views.
- Make comparable trials inspectable, including source link and missing metadata.
- Add a compute-cost summary that is visibly labeled as simulated.
- Add deterministic task manifests, mock shard assignments, input/output hashes,
  and verification results to each simulated job.
- Define the mock device-hour and cost assumptions returned by the API; do not
  claim measured savings.
- Add local demo reset behavior so repeated presentations start cleanly.
- Test sparse metadata and two-candidate jobs with different anchors.

Again, these are options rather than assigned tracks. Each contribution must be
independently reviewable so the project lead can keep only the strongest parts.

**Project Lead integration checkpoint at 4:00 PM**

- Run the full submit -> shard -> distribute -> verify -> return story.
- Confirm every displayed factor has a real source or an explicit unavailable
  state.

### Thursday, August 6: Hardening and Rehearsal

**Shared hardening pool**

- Stop adding major features by noon.
- Fix workflow blockers, unclear states, responsive defects, and demo data gaps.
- Pair-review each other's work and close test gaps.
- Run the clean-checkout setup on a second machine or fresh directory.
- Remove runtime dependencies on external fonts or other remote frontend assets.

**Project Lead**

- Freeze the demo data, score formula, API response shapes, and UI copy at noon.
- Write a 5-minute primary script and a 2-minute fallback script.
- Record a backup walkthrough.
- Prepare answers for data provenance, scoring, privacy, distributed execution,
  predictable cost, and what would be required for production validation.

### Friday, August 7: Demo Release

- Run the full suite and browser smoke test before any presentation.
- Tag or record the exact demo commit.
- Start the server from a clean terminal and keep a second terminal ready.
- Use only curated anchors and frozen protocol examples.
- Do not fetch remote data, install dependencies, or enable Firebase during the
  live demo.
- Keep the backup recording and screenshots available.

## Daily Operating Rhythm

- **9:15 AM:** 10-minute standup: yesterday, today, blocker, files being edited.
- **12:30 PM:** merge window for small completed pull requests.
- **4:00 PM:** integrated demo from `main`; no branch-only demos.
- **4:30 PM:** second merge window and next-day assignment update.
- **End of day:** project lead records current demo commit, test count, known
  issues, and the next morning's first task.

Escalate a blocker after 30 minutes. Do not silently substitute mock data for a
missing real field. Mark it unavailable and notify the project lead.

## Pull Request Checklist

Every pull request must be small enough to review in one sitting and include:

- [ ] One user-visible or testable outcome.
- [ ] Focused tests for changed backend behavior.
- [ ] Full test suite passing before merge.
- [ ] No generated data, credentials, PHI, or customer protocols committed.
- [ ] Screenshots for visual changes at desktop and mobile widths.
- [ ] Experimental estimate and simulation labels preserved.
- [ ] Documentation updated when an API or demo command changes.
- [ ] No unrelated formatting or refactoring.

## Demo Definition of Done

### Workflow

- [ ] Paste and `.txt`/`.md` upload both populate the protocol editor.
- [ ] A user can search and select a curated Trial2Vec anchor.
- [ ] One- and two-candidate jobs complete without page reload.
- [ ] Jobs visibly traverse all seven lifecycle states.
- [ ] Job history distinguishes active and completed work.
- [ ] Device assignments update during execution and clear after completion.
- [ ] Simulated device-hours and cost assumptions are inspectable.

### Results

- [ ] Results show five real Trial2Vec neighbors per candidate.
- [ ] Each factor shows weight, contribution, source, and availability.
- [ ] Comparison shows why candidate estimates differ.
- [ ] Missing metadata is visible and never replaced with invented values.
- [ ] ClinicalTrials.gov links work for enriched records.
- [ ] The phrase `Experimental demo estimate (not a validated clinical
  prediction)` appears beside every score.

### Reliability

- [ ] Full unit suite passes from a clean checkout.
- [ ] Browser smoke test passes at desktop and mobile viewport sizes.
- [ ] Unknown NCT IDs and malformed uploads fail clearly without crashing.
- [ ] Repeating the demo five times produces the expected lifecycle and results.
- [ ] A local reset command or restart returns the demo to a clean state.

### Presentation

- [ ] Primary and fallback scripts are rehearsed.
- [ ] A backup recording exists.
- [ ] Real Trial2Vec retrieval and mocked compute/scoring are described
  separately.
- [ ] No claim suggests clinical validation, production security, or real device
  execution.

## Current Implementation Baseline

| Capability | Status | Location |
|---|---|---|
| Imported clinical embeddings | Complete | `clinical/data/Emde/` |
| Local trial similarity search | Complete | `clinical/trial_search.py` |
| Evidence-source hash and provenance | Complete | `clinical/evidence_catalog.py` |
| Program-profile schema and input fingerprint | Complete | `clinical/schemas.py` |
| Clinical evidence API | Complete | `clinical/api.py` |
| Structured metadata importer | Complete | `clinical/import_metadata.py` |
| Structured metadata coverage | Partial | Bounded 25-study local demo catalog |
| Deterministic local evidence brief | Complete | `clinical/evidence_brief.py` |
| Claim source-reference verification | Complete | `clinical/claim_verifier.py` |
| Local reviewable brief workflow | Complete | `clinical/review_ledger.py` |
| Evidence-quality evaluation harness | Complete | `clinical/evaluate_claims.py` |
| Reviewer packet preparation | Complete | `clinical/review_packet.py` |
| Protocol draft coverage and change analysis | Complete | `clinical/protocol_analysis.py` |
| Simulated Trial2Vec distributed prediction demo | Complete | `clinical/demo_jobs.py` |
| Local demo workspace | Complete baseline; needs hardening | `clinical/static/` |
| Validated probability-of-success model | Blocked | Requires outcome data and qualified validation |
| Source-linked regulatory claims | Not started | Phase 2 |
| Authentication and tenant isolation | Not started | Phase 3 |
| Distributed clinical task execution | Not started | Phase 4; demo lifecycle is simulated only |

### Run Locally

```bash
venv/bin/python -m pip install -r clinical/requirements.txt
venv/bin/python clinical/import_trials.py clinical/data/Emde
venv/bin/python -m unittest discover -s tests -v
venv/bin/python -m uvicorn clinical.api:app --host 127.0.0.1 --port 8001
```

The clinical API is local and does not use Firebase.

## Demo Direction

The demo is a real-time clinical trial design workspace. A user drafts or
uploads a protocol, then receives bounded feedback as the draft changes:

- protocol completeness and structured design coverage
- source-backed precedent and evidence-gap signals
- clearly scoped language, design, and operational considerations
- change-by-change feedback that records what changed and which signals moved

This is not a static dashboard. The interface should debounce edits and submit
the current draft version for analysis without persisting customer content during
the local demo.

### Prediction Boundary

The current Emde dataset contains binary `sentiment` labels, not trial outcomes.
It cannot train, calibrate, or validate a probability-of-success model.

The demo may display a numeric `experimental demo estimate` only when it is
shown with its transparent heuristic factors: Trial2Vec similarity plus whatever
status, phase, enrollment, and intervention metadata is actually available from
the bounded ClinicalTrials.gov catalog. It must never be called a probability,
confidence interval, validated forecast, or projected increase or decrease in
success rate. Every output must state that it is not a clinical, operational,
or regulatory recommendation.

An approved historical outcome dataset, calibration protocol, and qualified
validation remain required before any predictive claim can be made.

## Product Vision

BioStonk is an enterprise clinical AI platform that gives teams auditable,
real-time feedback while they design clinical trial protocols. Its first workflow
supports evidence-backed protocol planning for orphan-drug and rare-disease
programs.

The product helps teams identify comparable programs, endpoint and trial-design
precedents, relevant patient populations and control designs, evidence gaps, and
the sources supporting each visible consideration. A future validated model may
estimate trial outcomes, but no such model exists in the current prototype.

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

- A drafted or uploaded protocol, with indication, disease subtype, modality,
  proposed population, intervention, comparator, endpoints, phase, and
  operational assumptions.
- Approved evidence sources: clinical-trial records, public regulatory material,
  scientific literature, natural-history studies, and customer-approved internal
  documents.
- User-selected filters: jurisdiction, date range, regulatory agency, and
  evidence types.

### Output

An auditable, continuously refreshed protocol feedback view containing:

- Protocol completeness and missing-information warnings.
- Comparable development programs with source-backed similarity context.
- Endpoint, population, comparator, and trial-design evidence considerations.
- Change deltas that describe altered coverage or evidence signals, not outcome
  probabilities.
- A reproducible analysis record showing draft hash, source versions, task
  results, and verification status.

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

## Post-Demo Assigned Deliverable

### Qualified Evaluation Set

The evaluator measures source-reference behavior and reports reviewer-supplied
support and applicability labels. It does not supply qualified judgments or
establish whether a claim is clinically correct, regulatorily relevant, or
complete.

Reviewer packets now prepare source-backed candidate excerpts for labeling, but
the packet itself is not an evaluation set and contains no reviewer judgments.

This is not a blocker for the one-week product demonstration. After the demo,
assemble an approved evaluation set with qualified reviewers:

- Define claim types and acceptance criteria for clinical and regulatory use.
- Create accepted, rejected, and uncertain examples from approved source sets.
- Record independent reviewer support and applicability labels.
- Require qualified human review before any external use of finalized material.

#### Definition of Done

- The evaluation set has documented source provenance and reviewer qualifications.
- Reviewers can assess source support and applicability independently.
- Results identify unsupported claim classes and evidence gaps.
- No external clinical or regulatory claim is released without required review.

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

## Long-Term Delivery Plan

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

## Long-Term Success Criteria

- A regulatory professional can create a program profile and receive a brief
  with inspectable source support for every material conclusion.
- Reviewers can reproduce an analysis from its recorded inputs and source
  versions.
- The system flags missing, conflicting, or insufficient evidence rather than
  presenting unsupported certainty.
- Customer data remains tenant-isolated and access-audited.
- Distributed execution produces the same verified task outputs as an approved
  baseline execution.