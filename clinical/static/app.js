const state = { previousDraft: null, activeJob: null, jobTimer: null, comparisonResults: [], computeReady: false };
const byId = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));

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

function updateDraftMetrics() {
  byId("anchor-metric").textContent = byId("anchor-nct").value.trim() || "Not set";
  byId("enrollment-metric").textContent = byId("planned-enrollment").value || "--";
  byId("sites-metric").textContent = byId("planned-sites").value || "--";
  byId("phase-metric").textContent = byId("study-phase").value.trim() || "Not set";
  const comparing = byId("compare-toggle").checked;
  byId("candidate-b-score").textContent = comparing ? "Draft" : "Off";
  byId("candidate-b-score").classList.toggle("subdued", !comparing);
  byId("candidate-b-caption").textContent = comparing ? "Ready to submit" : "Comparison not enabled";
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
  byId("coverage-metric").textContent = `${coverage.provided_design_field_count}/${coverage.required_design_field_count}`;
  byId("coverage-output").innerHTML = `<strong>${coverage.provided_design_field_count}/${coverage.required_design_field_count} design fields supplied</strong><p>Missing design fields</p><ul>${coverage.missing_design_fields.map(label).join("") || "<li>None</li>"}</ul><p>Missing operational fields</p><ul>${coverage.missing_operational_fields.map(label).join("") || "<li>None</li>"}</ul>`;
}

function label(value) { return `<li>${value.replaceAll("_", " ")}</li>`; }
function lifecycle(job) { byId("job-id").textContent = job.job_id; byId("job-detail").textContent = job.execution_notice; byId("job-state-metric").textContent = job.status; const index = job.lifecycle.indexOf(job.status); [...byId("lifecycle").children].forEach((item, i) => { item.className = i === index ? "current" : i < index ? "active" : ""; }); }

async function submitJob(event) {
  event.preventDefault();
  if (!state.computeReady) {
    byId("job-detail").textContent = "The compute pool is not ready. Check the topology status and worker processes.";
    return;
  }
  const candidates = [candidateFromForm("candidate-a")];
  if (byId("compare-toggle").checked) candidates.push(candidateFromForm("candidate-b", "-b"));
  const response = await fetch("/comparison-jobs", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({candidates}) });
  const job = await response.json();
  if (!response.ok) { byId("job-detail").textContent = job.detail || "Job could not be submitted."; return; }
  state.activeJob = job; state.comparisonResults = []; lifecycle(job); byId("results").classList.add("hidden"); loadJobs();
  byId("candidate-a-score").textContent = "Queued";
  byId("candidate-a-caption").textContent = "Waiting for allowlisted workers";
  byId("protocol-dialog").close();
  clearInterval(state.jobTimer); state.jobTimer = setInterval(pollJob, 1000);
  loadDevices();
}

async function pollJob() {
  const response = await fetch(`/comparison-jobs/${state.activeJob.job_id}`);
  if (!response.ok) {
    clearInterval(state.jobTimer);
    state.activeJob = null;
    byId("job-state-metric").textContent = "Restart";
    byId("job-detail").textContent = "The local server reloaded during this comparison. Run it again to restore the in-memory job.";
    return;
  }
  state.activeJob = await response.json(); lifecycle(state.activeJob); loadDevices(); loadJobs();
  byId("candidate-a-score").textContent = state.activeJob.status;
  byId("candidate-a-caption").textContent = `${state.activeJob.tasks.filter((task) => task.status === "completed").length}/${state.activeJob.tasks.length} replicas returned`;
  if (state.activeJob.status === "completed") { clearInterval(state.jobTimer); renderResults(state.activeJob.results, state.activeJob.verification); }
  if (state.activeJob.status === "failed") { clearInterval(state.jobTimer); byId("job-detail").textContent = state.activeJob.errors.join(" ") || "Verification failed."; }
}

function renderResults(results, verification) {
  state.comparisonResults = results;
  byId("results").classList.remove("hidden");
  byId("verification-output").classList.remove("hidden");
  byId("verification-output").innerHTML = `<strong>Verified aggregate</strong><dl><dt>Method</dt><dd>${verification.method.replaceAll("_", " ")}</dd><dt>Workers</dt><dd>${verification.worker_ids.length}</dd><dt>Verified replicas</dt><dd>${verification.verified_task_count}</dd><dt>Aggregate checksum</dt><dd class="mono">${verification.aggregate_checksum.slice(0, 16)}…</dd></dl>`;
  results.forEach((result) => {
    const suffix = result.candidate_id === "candidate-a" ? "a" : "b";
    byId(`candidate-${suffix}-score`).textContent = `${result.top_match_similarity}%`;
    byId(`candidate-${suffix}-caption`).textContent = "Top Trial2Vec match";
  });
  byId("result-candidates").innerHTML = results.map((result) => `<article class="result-panel"><p class="eyebrow">${result.candidate_id}</p><div class="score-line"><span class="score">${result.top_match_similarity}%</span><span class="score-caption">${result.comparison_label}</span></div><h3>Measured evidence</h3><table class="data-table"><thead><tr><th>Measurement</th><th>Value</th><th>Source</th></tr></thead><tbody>${result.measurements.map((measurement) => `<tr><td>${measurement.measurement}</td><td>${measurement.value}</td><td>${measurement.source}</td></tr>`).join("")}</tbody></table><h3>Similar historical trials</h3><table class="data-table"><thead><tr><th>NCT</th><th>Similarity</th><th>Status</th></tr></thead><tbody>${result.similar_historical_trials.map((trial) => `<tr><td>${trial.nct_id}</td><td>${(trial.similarity * 100).toFixed(1)}%</td><td>${trial.metadata?.overall_status || "Unavailable"}</td></tr>`).join("")}</tbody></table><h3>Data quality notes</h3><ul class="risk-list">${result.risk_indicators.map((item) => `<li>${item}</li>`).join("")}</ul><h3>Coverage prompts</h3><div class="recommendations">${result.recommendations.map((item) => `<p>${item}</p>`).join("")}</div></article>`).join("");
}

function analyzeWordAssociation() {
  const input = byId("association-word");
  const output = byId("word-association-output");
  const word = input.value.trim().toLocaleLowerCase();
  if (!/^[a-z][a-z-]*$/i.test(word)) {
    output.textContent = "Enter one word using letters or a hyphen.";
    return;
  }
  const escapedWord = word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const countPattern = new RegExp(`\\b${escapedWord}\\b`, "gi");
  const searchPattern = new RegExp(`\\b${escapedWord}\\b`, "i");
  const protocolText = byId("protocol-text").value;
  const protocolMatches = protocolText.match(countPattern)?.length || 0;
  const comparableRecords = state.comparisonResults.flatMap((result) => result.similar_historical_trials || []);
  const comparableMatches = comparableRecords.filter((trial) => searchPattern.test(JSON.stringify(trial.metadata || {}))).length;
  output.replaceChildren();
  const count = document.createElement("strong");
  count.textContent = `${protocolMatches} protocol mention${protocolMatches === 1 ? "" : "s"}`;
  const explanation = document.createElement("span");
  explanation.textContent = state.comparisonResults.length
    ? `${comparableMatches} of ${comparableRecords.length} returned comparables include the word in available metadata. This is literal text matching, not outcome association.`
    : "Run a comparison to inspect the word across returned comparable metadata. This is literal text matching, not outcome association.";
  output.append(count, explanation);
}

async function loadJobs() {
  const jobs = await (await fetch("/comparison-jobs/history")).json();
  byId("job-list").innerHTML = jobs.map((job) => `<div class="job-row"><strong>${job.job_id}</strong><span>${job.tasks.length} replicas</span><span class="job-status">${job.status}</span></div>`).join("");
}

async function loadDevices() {
  try {
    const response = await fetch("/demo/devices");
    if (!response.ok) return;
    const devices = await response.json();
    const connected = devices.filter((device) => device.connected);
    byId("device-count").textContent = connected.length;
    byId("devices-grid").innerHTML = devices.map((device) => {
      const capacity = device.connected && device.cpu_cores != null
        ? `${esc(device.cpu_cores)} cores · ${device.memory_gb ?? "Unknown"} GB`
        : "--";
      const detail = device.connected
        ? `${esc(device.device_id)} · ${esc(device.type)}`
        : `Approved endpoint — connect a worker as ${esc(device.device_id)}`;
      const availability = device.connected ? device.availability : "not connected";
      const statusRow = device.connected ? "" : "<dt>Status</dt><dd>waiting for first connection</dd>";
      return `<article class="device${device.connected ? "" : " device-expected"}"><h3>${esc(device.name)}</h3><p>${detail}</p><dl><dt>Allowlist</dt><dd>${device.allowlisted ? "Allowed" : "Not allowed"}</dd><dt>Capacity</dt><dd>${capacity}</dd><dt>Availability</dt><dd class="availability ${availability.replaceAll(" ", "-")}">${availability}</dd>${statusRow}<dt>Assigned tasks</dt><dd>${device.assigned_tasks.length}</dd></dl></article>`;
    }).join("");
  } catch {
    // Ignore transient API unavailability; the grid keeps its last state.
  }
}

async function loadComputeReadiness() {
  const response = await fetch("/compute/readiness");
  if (!response.ok) return;
  const readiness = await response.json();
  state.computeReady = readiness.ready;
  byId("submit-comparison").disabled = !readiness.ready;
  byId("compute-mode").textContent = readiness.mode === "two-host-lan-pilot" ? "Two-host LAN pilot" : "Single-host development";
  const notice = byId("compute-readiness-notice");
  if (readiness.ready && readiness.mode === "two-host-lan-pilot") {
    notice.innerHTML = `<strong>LAN pilot ready.</strong> ${readiness.active_worker_count} allowlisted workers on ${readiness.distinct_active_host_count} distinct hosts report the same artifact checksum. This is not production hardware approval or attestation.`;
  } else if (readiness.ready) {
    notice.innerHTML = `<strong>Single-host development mode.</strong> ${readiness.active_worker_count} worker processes are available on ${readiness.distinct_active_host_count} host. This validates orchestration only; it is not a two-laptop test.`;
  } else {
    notice.innerHTML = `<strong>Compute pool not ready.</strong> ${readiness.blockers.join(" ")}`;
  }
}

let debounce; byId("protocol-form").addEventListener("input", () => { updateDraftMetrics(); clearTimeout(debounce); debounce = setTimeout(analyzeDraft, 600); });
byId("protocol-form").addEventListener("submit", submitJob);
byId("compare-toggle").addEventListener("change", (event) => { byId("candidate-b").classList.toggle("hidden", !event.target.checked); updateDraftMetrics(); });
byId("protocol-file").addEventListener("change", async (event) => { const file = event.target.files[0]; if (file) byId("protocol-text").value = await file.text(); analyzeDraft(); });
byId("open-protocol").addEventListener("click", () => byId("protocol-dialog").showModal());
byId("close-protocol").addEventListener("click", () => byId("protocol-dialog").close());
byId("protocol-dialog").addEventListener("click", (event) => { if (event.target === byId("protocol-dialog")) byId("protocol-dialog").close(); });
byId("devices-button").addEventListener("click", () => byId("devices").scrollIntoView({ behavior: "smooth" }));
byId("analyze-word").addEventListener("click", analyzeWordAssociation);
byId("association-word").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); analyzeWordAssociation(); } });
byId("close-gallery").addEventListener("click", () => { byId("model-gallery").open = false; byId("model-gallery").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
updateDraftMetrics(); analyzeDraft(); loadDevices(); loadJobs(); loadComputeReadiness();
setInterval(loadComputeReadiness, 5000);
setInterval(loadDevices, 3000);