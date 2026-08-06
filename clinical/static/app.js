const state = { previousDraft: null, activeJob: null, jobTimer: null, lastAnnouncedStatus: null };
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
  byId("coverage-output").setAttribute("aria-busy", "true");
  announce("Analyzing protocol draft coverage.");
  const response = await fetch("/protocol-drafts/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draft, previous_draft: state.previousDraft }) });
  if (!response.ok) {
    byId("analysis-state").textContent = "Error";
    byId("coverage-output").setAttribute("aria-busy", "false");
    announce("Protocol analysis failed.");
    return;
  }
  const analysis = await response.json(); state.previousDraft = draft;
  const coverage = analysis.coverage;
  byId("analysis-state").textContent = "Live";
  byId("coverage-output").innerHTML = `<strong>${coverage.provided_design_field_count}/${coverage.required_design_field_count} design fields supplied</strong><p>Missing design fields</p><ul>${coverage.missing_design_fields.map(label).join("") || "<li>None</li>"}</ul><p>Missing operational fields</p><ul>${coverage.missing_operational_fields.map(label).join("") || "<li>None</li>"}</ul>`;
  byId("coverage-output").setAttribute("aria-busy", "false");
  const missingCount = coverage.missing_design_fields.length + coverage.missing_operational_fields.length;
  announce(`Protocol coverage updated. ${missingCount === 0 ? "All fields supplied." : `${missingCount} fields missing.`}`);
}

function label(value) { return `<li>${value.replaceAll("_", " ")}</li>`; }
function lifecycle(job) {
  byId("job-id").textContent = job.job_id;
  byId("job-detail").textContent = job.execution_notice;
  const index = job.lifecycle.indexOf(job.status);
  [...byId("lifecycle").children].forEach((item, i) => { item.className = i === index ? "current" : i < index ? "active" : ""; });
  if (state.lastAnnouncedStatus !== job.status) {
    state.lastAnnouncedStatus = job.status;
    announce(`Job ${job.job_id}: ${job.status}.`);
  }
}

function announce(message) {
  const region = byId("sr-status");
  if (!region) return;
  region.textContent = "";
  requestAnimationFrame(() => { region.textContent = message; });
}

function setFormDisabled(disabled, reason) {
  const form = byId("protocol-form");
  const submitButton = byId("submit-job");
  const controls = form.querySelectorAll("input, textarea, select, button");
  controls.forEach((control) => {
    if (control.classList.contains("anchor-search")) return; // managed by AnchorCombobox
    control.disabled = disabled;
  });
  anchorA.setDisabled(disabled);
  anchorB.setDisabled(disabled);
  submitButton.disabled = disabled;
  submitButton.setAttribute("aria-disabled", disabled ? "true" : "false");
  if (disabled && reason) {
    announce(reason);
  }
}

async function submitJob(event) {
  event.preventDefault();
  const candidates = [candidateFromForm("candidate-a")];
  if (byId("compare-toggle").checked) candidates.push(candidateFromForm("candidate-b", "-b"));
  const missingAnchors = candidates.filter((c) => !c.anchor_nct_id);
  if (missingAnchors.length > 0) {
    byId("job-detail").textContent = "Please select a Trial2Vec anchor for every candidate.";
    return;
  }
  setFormDisabled(true, "Submitting prediction job. Please wait.");
  byId("job-detail").textContent = "Submitting prediction job...";
  byId("jobs").setAttribute("aria-busy", "true");
  const response = await fetch("/demo/prediction-jobs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ candidates }) });
  const job = await response.json();
  if (!response.ok) {
    setFormDisabled(false);
    byId("jobs").setAttribute("aria-busy", "false");
    byId("job-detail").textContent = job.detail || "Job could not be submitted.";
    return;
  }
  state.activeJob = job; lifecycle(job); byId("results").classList.add("hidden"); loadJobs();
  clearInterval(state.jobTimer); state.jobTimer = setInterval(advanceJob, 650);
  loadDevices();
}

async function advanceJob() {
  const response = await fetch(`/demo/prediction-jobs/${state.activeJob.job_id}/advance`, { method: "POST" });
  state.activeJob = await response.json(); lifecycle(state.activeJob); loadDevices(); loadJobs();
  if (state.activeJob.status === "completed") {
    clearInterval(state.jobTimer);
    renderResults(state.activeJob.results);
    setFormDisabled(false);
    byId("jobs").setAttribute("aria-busy", "false");
    state.lastAnnouncedStatus = null;
    announce("Prediction job completed. Form controls are available.");
  }
}

function renderResults(results) {
  byId("results").classList.remove("hidden");
  byId("result-candidates").innerHTML = results.map((result) => `<article class="result-panel"><p class="eyebrow">${result.candidate_id}</p><div class="score-line"><span class="score">${result.experimental_demo_estimate}</span><span class="score-caption">${result.score_label}</span></div><h3>Contributing factors</h3><table class="data-table"><thead><tr><th>Factor</th><th>Value</th><th>Weight</th><th>Contribution</th><th>Source type</th><th>Availability</th></tr></thead><tbody>${result.factors.map((factor) => `<tr><td>${factor.factor}</td><td>${factor.value ?? "Unavailable"}</td><td>${factor.weight}</td><td>${factor.contribution ?? "—"}</td><td>${factor.source_type}</td><td>${factor.availability}</td></tr>`).join("")}</tbody></table><h3>Similar historical trials</h3><table class="data-table"><thead><tr><th>NCT</th><th>Similarity</th><th>Status</th><th>Phase</th></tr></thead><tbody>${result.similar_historical_trials.map((trial) => `<tr><td>${trial.nct_id}</td><td>${trial.similarity}</td><td>${trial.metadata?.overall_status || "Unavailable"}</td><td>${trial.metadata?.phases?.join(", ") || "Unavailable"}</td></tr>`).join("")}</tbody></table><h3>Demo indicators</h3><ul class="risk-list">${result.risk_indicators.map((item) => `<li>${item}</li>`).join("")}</ul><h3>Coverage prompts</h3><div class="recommendations">${result.recommendations.map((item) => `<p>${item}</p>`).join("")}</div></article>`).join("");
}

async function loadJobs() {
  const jobs = await (await fetch("/demo/prediction-jobs/history")).json();
  byId("job-list").innerHTML = jobs.map((job) => `<div class="job-row"><strong>${job.job_id}</strong><span>${job.tasks.length} candidate${job.tasks.length === 1 ? "" : "s"}</span><span class="job-status">${job.status}</span></div>`).join("");
}

async function loadDevices() {
  const devices = await (await fetch("/demo/devices")).json();
  byId("devices-grid").innerHTML = devices.map((device) => `<article class="device"><h3>${device.name}</h3><p>${device.device_id} · ${device.type}</p><dl><dt>Approval</dt><dd>${device.approved ? "Approved" : "Not approved"}</dd><dt>Capacity</dt><dd>${device.cpu_cores} cores · ${device.memory_gb} GB</dd><dt>Availability</dt><dd class="availability ${device.availability}">${device.availability}</dd><dt>Assigned tasks</dt><dd>${device.assigned_tasks.length}</dd></dl></article>`).join("");
}

class AnchorCombobox {
  constructor(containerId, hiddenInputId, initialNct) {
    this.container = byId(containerId);
    this.searchInput = this.container.querySelector(".anchor-search");
    this.hiddenInput = byId(hiddenInputId);
    this.listbox = this.container.querySelector(".anchor-list");
    this.debounceTimer = null;
    this.options = [];
    this.activeIndex = -1;
    this.selectedNct = initialNct || "";
    if (this.selectedNct) {
      this.hiddenInput.value = this.selectedNct;
      this.searchInput.value = this.selectedNct;
    }
    this.searchInput.addEventListener("input", () => this.onInput());
    this.searchInput.addEventListener("keydown", (event) => this.onKeyDown(event));
    this.searchInput.addEventListener("blur", () => this.onBlur());
    this.searchInput.addEventListener("focus", () => { if (this.searchInput.disabled) return; if (this.searchInput.value.trim()) this.fetchAnchors(this.searchInput.value.trim()); });
    this.listbox.addEventListener("mousedown", (event) => this.onOptionClick(event));
  }

  async onInput() {
    const query = this.searchInput.value.trim();
    this.hiddenInput.value = "";
    this.selectedNct = "";
    clearTimeout(this.debounceTimer);
    this.setLoading(true);
    this.debounceTimer = setTimeout(() => this.fetchAnchors(query), 200);
  }

  async fetchAnchors(query) {
    const url = query ? `/demo/anchors?query=${encodeURIComponent(query)}&limit=20` : "/demo/anchors?limit=20";
    if (query) announce("Loading anchor trials.");
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Anchor search failed");
      const anchors = await response.json();
      this.renderOptions(anchors);
    } catch (error) {
      this.renderOptions([]);
      announce("Anchor search failed.");
    } finally {
      this.setLoading(false);
    }
  }

  renderOptions(anchors) {
    this.options = anchors;
    this.activeIndex = -1;
    if (anchors.length === 0) {
      this.listbox.innerHTML = `<li class="anchor-empty" role="option" aria-selected="false">No matching anchor trials</li>`;
      this.openListbox();
      return;
    }
    this.listbox.innerHTML = anchors.map((anchor, index) => {
      const metaParts = [
        anchor.indication,
        anchor.phase,
        anchor.study_type,
        anchor.overall_status,
      ].filter(Boolean);
      const metaText = metaParts.length ? ` · ${metaParts.join(" · ")}` : "";
      const titleText = anchor.title ? ` — ${anchor.title}` : "";
      const unavailable = anchor.metadata_available ? "" : " · metadata unavailable";
      return `<li id="${this.optionId(index)}" role="option" aria-selected="false" data-index="${index}"><strong>${anchor.nct_id}</strong><span class="anchor-meta">${titleText}${metaText}${unavailable}</span></li>`;
    }).join("");
    this.openListbox();
  }

  optionId(index) { return `${this.container.id}-option-${index}`; }

  openListbox() {
    this.listbox.classList.add("open");
    this.searchInput.setAttribute("aria-expanded", "true");
  }

  closeListbox() {
    this.listbox.classList.remove("open");
    this.searchInput.setAttribute("aria-expanded", "false");
    this.searchInput.setAttribute("aria-activedescendant", "");
    this.activeIndex = -1;
  }

  setLoading(isLoading) {
    this.container.classList.toggle("loading", isLoading);
    this.searchInput.setAttribute("aria-busy", isLoading ? "true" : "false");
  }

  setDisabled(isDisabled) {
    this.searchInput.disabled = isDisabled;
    if (isDisabled) this.closeListbox();
  }

  onKeyDown(event) {
    if (this.options.length === 0 && event.key !== "Escape") return;
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        this.moveActive(1);
        break;
      case "ArrowUp":
        event.preventDefault();
        this.moveActive(-1);
        break;
      case "Enter":
        event.preventDefault();
        if (this.activeIndex >= 0) {
          this.selectOption(this.activeIndex);
        }
        break;
      case "Escape":
        this.closeListbox();
        break;
    }
  }

  moveActive(delta) {
    if (this.options.length === 0) return;
    this.activeIndex = (this.activeIndex + delta + this.options.length) % this.options.length;
    this.updateActiveDescendant();
  }

  updateActiveDescendant() {
    [...this.listbox.children].forEach((child, index) => {
      const selected = index === this.activeIndex;
      child.setAttribute("aria-selected", selected ? "true" : "false");
      child.classList.toggle("active", selected);
    });
    if (this.activeIndex >= 0) {
      this.searchInput.setAttribute("aria-activedescendant", this.optionId(this.activeIndex));
      this.listbox.children[this.activeIndex].scrollIntoView({ block: "nearest" });
    }
  }

  onOptionClick(event) {
    const option = event.target.closest("[data-index]");
    if (!option) return;
    this.selectOption(Number(option.dataset.index));
  }

  selectOption(index) {
    const anchor = this.options[index];
    if (!anchor) return;
    this.selectedNct = anchor.nct_id;
    this.hiddenInput.value = anchor.nct_id;
    this.searchInput.value = anchor.nct_id;
    this.closeListbox();
    this.searchInput.setAttribute("aria-invalid", "false");
  }

  onBlur() {
    setTimeout(() => {
      this.closeListbox();
      this.searchInput.setAttribute("aria-invalid", this.hiddenInput.value ? "false" : "true");
    }, 150);
  }
}

const anchorA = new AnchorCombobox("anchor-combobox-a", "anchor-nct", "NCT02545127");
const anchorB = new AnchorCombobox("anchor-combobox-b", "anchor-nct-b", "NCT02545127");

let debounce; byId("protocol-form").addEventListener("input", (event) => { if (event.target.classList.contains("anchor-search")) return; clearTimeout(debounce); debounce = setTimeout(analyzeDraft, 600); });
byId("protocol-form").addEventListener("submit", submitJob);
byId("compare-toggle").addEventListener("change", (event) => byId("candidate-b").classList.toggle("hidden", !event.target.checked));
byId("protocol-file").addEventListener("change", async (event) => { const file = event.target.files[0]; if (file) byId("protocol-text").value = await file.text(); analyzeDraft(); });
analyzeDraft(); loadDevices(); loadJobs();
