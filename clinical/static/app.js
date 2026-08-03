const state = { previousDraft: null, activeJob: null, jobTimer: null };
const byId = (id) => document.getElementById(id);

function draftFromForm(suffix = "") {
  const value = (id) => byId(`${id}${suffix}`).value.trim();
  const number = (id) => { const raw = value(id); return raw ? Number(raw) : null; };
  return {
    protocol_text: value("protocol-text"), title: null, indication: value("indication"), study_phase: value("study-phase"),
    population: value("population"), intervention: value("intervention"), intervention_type: value("intervention-type"),
    comparator: value("comparator"), primary_endpoint: value("primary-endpoint"), planned_enrollment: number("planned-enrollment"), planned_site_count: number("planned-sites")
  };
}

function candidateFromForm(id, suffix = "") {
  const draft = suffix ? { ...draftFromForm(), protocol_text: byId("protocol-text-b").value.trim(), planned_enrollment: Number(byId("planned-enrollment-b").value) || null } : draftFromForm();
  return { candidate_id: id, anchor_nct_id: byId(`anchor-nct${suffix}`).value.trim(), draft };
}

async function analyzeDraft() {
  const draft = draftFromForm();
  if (!draft.protocol_text) return;
  byId("analysis-state").textContent = "Analyzing";
  const response = await fetch("/protocol-drafts/analyze", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ draft, previous_draft: state.previousDraft }) });
  if (!response.ok) return;
  const analysis = await response.json(); state.previousDraft = draft;
  const coverage = analysis.coverage;
  byId("analysis-state").textContent = "Live";
  byId("coverage-output").innerHTML = `<strong>${coverage.provided_design_field_count}/${coverage.required_design_field_count} design fields supplied</strong><p>Missing design fields</p><ul>${coverage.missing_design_fields.map(label).join("") || "<li>None</li>"}</ul><p>Missing operational fields</p><ul>${coverage.missing_operational_fields.map(label).join("") || "<li>None</li>"}</ul>`;
}

function label(value) { return `<li>${value.replaceAll("_", " ")}</li>`; }
function lifecycle(job) { byId("job-id").textContent = job.job_id; byId("job-detail").textContent = job.execution_notice; const index = job.lifecycle.indexOf(job.status); [...byId("lifecycle").children].forEach((item, i) => { item.className = i === index ? "current" : i < index ? "active" : ""; }); }

async function submitJob(event) {
  event.preventDefault();
  const candidates = [candidateFromForm("candidate-a")];
  if (byId("compare-toggle").checked) candidates.push(candidateFromForm("candidate-b", "-b"));
  const response = await fetch("/demo/prediction-jobs", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({candidates}) });
  const job = await response.json();
  if (!response.ok) { byId("job-detail").textContent = job.detail || "Job could not be submitted."; return; }
  state.activeJob = job; lifecycle(job); byId("results").classList.add("hidden"); loadJobs();
  clearInterval(state.jobTimer); state.jobTimer = setInterval(advanceJob, 650);
  loadDevices();
}

async function advanceJob() {
  const response = await fetch(`/demo/prediction-jobs/${state.activeJob.job_id}/advance`, {method:"POST"});
  state.activeJob = await response.json(); lifecycle(state.activeJob); loadDevices(); loadJobs();
  if (state.activeJob.status === "completed") { clearInterval(state.jobTimer); renderResults(state.activeJob.results); }
}

function renderResults(results) {
  byId("results").classList.remove("hidden");
  byId("result-candidates").innerHTML = results.map((result) => `<article class="result-panel"><p class="eyebrow">${result.candidate_id}</p><div class="score-line"><span class="score">${result.experimental_demo_estimate}</span><span class="score-caption">${result.score_label}</span></div><h3>Contributing factors</h3><table class="data-table"><thead><tr><th>Factor</th><th>Value</th><th>Weight</th></tr></thead><tbody>${result.factors.map((factor) => `<tr><td>${factor.factor}</td><td>${factor.value ?? "Unavailable"}</td><td>${factor.weight}</td></tr>`).join("")}</tbody></table><h3>Similar historical trials</h3><table class="data-table"><thead><tr><th>NCT</th><th>Similarity</th><th>Status</th><th>Phase</th></tr></thead><tbody>${result.similar_historical_trials.map((trial) => `<tr><td>${trial.nct_id}</td><td>${trial.similarity}</td><td>${trial.metadata?.overall_status || "Unavailable"}</td><td>${trial.metadata?.phases?.join(", ") || "Unavailable"}</td></tr>`).join("")}</tbody></table><h3>Demo indicators</h3><ul class="risk-list">${result.risk_indicators.map((item) => `<li>${item}</li>`).join("")}</ul><h3>Coverage prompts</h3><div class="recommendations">${result.recommendations.map((item) => `<p>${item}</p>`).join("")}</div></article>`).join("");
}

async function loadJobs() {
  const jobs = await (await fetch("/demo/prediction-jobs/history")).json();
  byId("job-list").innerHTML = jobs.map((job) => `<div class="job-row"><strong>${job.job_id}</strong><span>${job.tasks.length} candidate${job.tasks.length === 1 ? "" : "s"}</span><span class="job-status">${job.status}</span></div>`).join("");
}

async function loadDevices() {
  const devices = await (await fetch("/demo/devices")).json();
  byId("devices-grid").innerHTML = devices.map((device) => `<article class="device"><h3>${device.name}</h3><p>${device.device_id} · ${device.type}</p><dl><dt>Approval</dt><dd>${device.approved ? "Approved" : "Not approved"}</dd><dt>Capacity</dt><dd>${device.cpu_cores} cores · ${device.memory_gb} GB</dd><dt>Availability</dt><dd class="availability ${device.availability}">${device.availability}</dd><dt>Assigned tasks</dt><dd>${device.assigned_tasks.length}</dd></dl></article>`).join("");
}

let debounce; byId("protocol-form").addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(analyzeDraft, 600); });
byId("protocol-form").addEventListener("submit", submitJob);
byId("compare-toggle").addEventListener("change", (event) => byId("candidate-b").classList.toggle("hidden", !event.target.checked));
byId("protocol-file").addEventListener("change", async (event) => { const file = event.target.files[0]; if (file) byId("protocol-text").value = await file.text(); analyzeDraft(); });
analyzeDraft(); loadDevices(); loadJobs();