const ACTIVE_TRIAL_ID = "NCT02545127";
const state = { previousDraft: null, activeJob: null, jobTimer: null, comparisonResults: [], computeReady: false, activeDocument: "protocol", trialLoaded: false, documentExtracting: false };
const byId = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
const plural = (value, singular, pluralForm) => { const count = Number(value) || 0; return `${count} ${count === 1 ? singular : pluralForm}`; };
const controlsList = (items) => (!items || !items.length) ? "" : `<ul class="production-controls">${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
const localTextExtensions = new Set(["txt", "md", "markdown", "xml", "yaml", "yml", "log", "tex", "rst", "json", "jsonl", "ndjson", "html", "htm", "csv", "tsv"]);
const maxDocumentBytes = 25 * 1024 * 1024;
const signalCatalog = [
  { phrase: "randomized", delta: 5, detail: "Random allocation contributes a positive simulated design signal." },
  { phrase: "double-blind", delta: 5, detail: "Masking contributes a positive simulated bias-control signal." },
  { phrase: "placebo-controlled", delta: 4, detail: "A placebo comparator strengthens the simulated design signal." },
  { phrase: "multicenter", delta: 3, detail: "Multiple sites contribute a positive simulated generalizability signal." },
  { phrase: "primary outcomes", delta: 4, detail: "Declared primary outcomes improve simulated endpoint clarity." },
  { phrase: "secondary outcomes", delta: 2, detail: "Declared secondary outcomes add supporting endpoint detail." },
  { phrase: "adverse events", delta: 3, detail: "Explicit adverse-event monitoring contributes a positive safety signal." },
  { phrase: "terminated", delta: -10, detail: "A terminated status contributes a strong negative historical signal." },
  { phrase: "4 participants", delta: -8, detail: "Very low enrollment contributes a negative evidence-volume signal." },
  { phrase: "not specified", delta: -3, detail: "Missing structured detail reduces the simulated completeness signal." }
];

const trialDocuments = {
  protocol: {
    label: "Protocol synopsis",
    baseScore: 68,
    html: `<h2>Protocol synopsis</h2><p>This Phase 2 study evaluates an investigational therapy in adults with a genetically confirmed rare disease. The trial uses a <mark class="positive">randomized, double-blind, placebo-controlled design</mark> to assess clinical benefit over 24 weeks.</p><h3>Objectives and endpoints</h3><p>The primary objective is to measure change from baseline in the validated functional outcome score at Week 24. A <mark class="positive">pre-specified primary endpoint</mark> and two ranked secondary endpoints will be analyzed under a hierarchical testing procedure.</p><p>Approximately 80 participants will be enrolled across four specialist sites. The proposed sample size is supported by historical variance estimates, although <mark>limited prior natural-history data</mark> may increase uncertainty in the assumed effect size.</p><h3>Study conduct</h3><p>Participants will be assigned 1:1 and stratified by baseline severity. An <mark class="positive">independent data monitoring committee</mark> will review unblinded safety data at defined intervals. Site training and centralized outcome assessment are intended to reduce inter-rater variability.</p><p>The 24-week controlled period will be followed by an open-label extension. Because the study serves a geographically dispersed population, <mark>travel burden for repeated site visits</mark> remains an operational risk.</p>`,
    signals: [
      { phrase: "randomized, double-blind, placebo-controlled design", delta: 9, detail: "Controlled allocation and masking strengthen the simulated design signal." },
      { phrase: "pre-specified primary endpoint", delta: 6, detail: "A declared endpoint reduces ambiguity in the analysis plan." },
      { phrase: "independent data monitoring committee", delta: 4, detail: "Independent oversight contributes a positive operational signal." },
      { phrase: "limited prior natural-history data", delta: -7, detail: "Sparse historical evidence increases effect-size uncertainty." },
      { phrase: "travel burden for repeated site visits", delta: -4, detail: "Participant burden may affect recruitment and retention." }
    ]
  },
  eligibility: {
    label: "Eligibility criteria",
    baseScore: 64,
    html: `<h2>Eligibility criteria</h2><h3>Inclusion criteria</h3><ul><li>Adults 18 to 70 years of age with genetically confirmed target disease.</li><li><mark class="positive">Documented functional decline during the prior 12 months</mark>.</li><li>Baseline functional outcome score within the protocol-defined range.</li><li>Stable standard-of-care therapy for at least eight weeks before randomization.</li></ul><h3>Exclusion criteria</h3><ul><li>Clinically significant hepatic, renal, or cardiovascular disease.</li><li>Prior exposure to the investigational therapy.</li><li>Participation in another interventional study within 60 days.</li><li><mark>Broad exclusion of common stable comorbidities</mark>.</li></ul><p>Eligibility will be confirmed through central review. The criteria aim to identify a measurable population, but <mark>narrow biomarker requirements</mark> may constrain recruitment at lower-volume sites.</p>`,
    signals: [
      { phrase: "Documented functional decline during the prior 12 months", delta: 6, detail: "Recent progression may improve endpoint sensitivity." },
      { phrase: "Broad exclusion of common stable comorbidities", delta: -5, detail: "Broad exclusions can reduce recruitment and generalizability." },
      { phrase: "narrow biomarker requirements", delta: -6, detail: "A narrow eligible population raises recruitment risk." }
    ]
  },
  statistical: {
    label: "Statistical plan",
    baseScore: 72,
    html: `<h2>Statistical analysis plan</h2><p>The primary analysis will compare treatment groups using a mixed model for repeated measures. The model includes treatment, visit, treatment-by-visit interaction, baseline score, and stratification factors.</p><p>A <mark class="positive">hierarchical testing procedure controls family-wise type I error</mark> across the primary and ranked secondary endpoints. The primary estimand addresses the treatment effect regardless of discontinuation, with intercurrent events handled through the treatment-policy strategy.</p><p><mark class="positive">Multiple imputation under missing-at-random assumptions</mark> will support the main analysis, with tipping-point analyses assessing departures from that assumption. The plan includes one blinded sample-size re-estimation, but <mark>the assumed treatment effect is based on a small external cohort</mark>.</p>`,
    signals: [
      { phrase: "hierarchical testing procedure controls family-wise type I error", delta: 7, detail: "Multiplicity is addressed with a pre-specified testing order." },
      { phrase: "Multiple imputation under missing-at-random assumptions", delta: 4, detail: "A declared missing-data strategy improves analysis completeness." },
      { phrase: "the assumed treatment effect is based on a small external cohort", delta: -8, detail: "A small external cohort makes power assumptions less stable." }
    ]
  },
  safety: {
    label: "Safety monitoring",
    baseScore: 70,
    html: `<h2>Safety monitoring plan</h2><p>Adverse events will be collected from consent through 30 days after the final dose. Investigators will grade severity and assess causality using the protocol-defined criteria.</p><p>An <mark class="positive">independent data monitoring committee will review unblinded data quarterly</mark> and after the first 20 participants complete four weeks of treatment. Predefined stopping rules address serious hypersensitivity, liver injury, and unexpected mortality.</p><p>Sites must report serious adverse events within 24 hours. Central laboratory alerts will be reviewed continuously, with <mark class="positive">automatic escalation of protocol-defined laboratory thresholds</mark>. The current draft has <mark>no pediatric long-term follow-up strategy</mark> because enrollment is restricted to adults.</p>`,
    signals: [
      { phrase: "independent data monitoring committee will review unblinded data quarterly", delta: 7, detail: "Scheduled independent review strengthens safety oversight." },
      { phrase: "automatic escalation of protocol-defined laboratory thresholds", delta: 5, detail: "Automatic escalation supports consistent signal detection." },
      { phrase: "no pediatric long-term follow-up strategy", delta: -3, detail: "The omitted population plan limits future evidence scope." }
    ]
  }
};

function initializeDocument(documentData) {
  const plainText = documentData.html.replace(/<[^>]+>/g, " ");
  documentData.initialWordCount = plainText.trim().split(/\s+/).filter(Boolean).length;
  documentData.initialSignalTotal = documentData.signals.reduce((total, signal) => total + signal.delta, 0);
}

Object.values(trialDocuments).forEach(initializeDocument);

function signalsForText(text) {
  const normalized = text.toLocaleLowerCase();
  return signalCatalog.filter((signal) => normalized.includes(signal.phrase.toLocaleLowerCase()));
}

function signalDescriptor(signal) {
  let hash = 0;
  for (const character of signal.phrase.toLocaleLowerCase()) hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  const magnitude = Math.abs(signal.delta);
  return {
    ...signal,
    signalId: `signal-${Math.abs(hash)}`,
    severity: magnitude >= 7 ? "extreme" : magnitude >= 4 ? "high" : "moderate"
  };
}

function signalMark(signal, text) {
  const mark = document.createElement("mark");
  mark.className = `${signal.delta > 0 ? "positive " : ""}severity-${signal.severity}`;
  mark.dataset.signalId = signal.signalId;
  mark.tabIndex = -1;
  mark.textContent = text;
  return mark;
}

function editorTextNodes() {
  const editor = byId("trial-document-editor");
  const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => node.parentElement?.closest(".document-editor-title") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  return nodes;
}

function editorCaretOffset() {
  const selection = window.getSelection();
  if (!selection?.rangeCount || !byId("trial-document-editor").contains(selection.anchorNode)) return null;
  let offset = 0;
  for (const node of editorTextNodes()) {
    if (node === selection.anchorNode) return offset + selection.anchorOffset;
    offset += node.textContent.length;
  }
  return null;
}

function restoreEditorCaret(offset) {
  if (offset === null) return;
  const selection = window.getSelection();
  const range = document.createRange();
  let remaining = offset;
  for (const node of editorTextNodes()) {
    if (remaining <= node.textContent.length) {
      range.setStart(node, remaining);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      return;
    }
    remaining -= node.textContent.length;
  }
}

function refreshEditorHighlights(signals) {
  const editor = byId("trial-document-editor");
  const caretOffset = editorCaretOffset();
  editor.querySelectorAll("mark").forEach((mark) => mark.replaceWith(document.createTextNode(mark.textContent)));
  editor.normalize();
  if (!signals.length) {
    restoreEditorCaret(caretOffset);
    return;
  }

  const sortedSignals = [...signals].sort((left, right) => right.phrase.length - left.phrase.length);
  const escapedPhrases = sortedSignals.map((signal) => signal.phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(escapedPhrases.join("|"), "gi");
  for (const node of editorTextNodes()) {
    const text = node.textContent;
    const matches = [...text.matchAll(pattern)];
    if (!matches.length) continue;
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    for (const match of matches) {
      const signal = sortedSignals.find((candidate) => candidate.phrase.toLocaleLowerCase() === match[0].toLocaleLowerCase());
      fragment.append(document.createTextNode(text.slice(cursor, match.index)), signalMark(signal, match[0]));
      cursor = match.index + match[0].length;
    }
    fragment.append(document.createTextNode(text.slice(cursor)));
    node.replaceWith(fragment);
  }
  restoreEditorCaret(caretOffset);
}

function jumpToSignal(signalId) {
  const editor = byId("trial-document-editor");
  const target = editor.querySelector(`mark[data-signal-id="${signalId}"]`);
  if (!target) return;
  editor.querySelectorAll("mark.is-jump-target").forEach((mark) => mark.classList.remove("is-jump-target"));
  target.classList.add("is-jump-target");
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.focus({ preventScroll: true });
  window.setTimeout(() => target.classList.remove("is-jump-target"), 1800);
}

function highlightedText(text, signals) {
  if (!signals.length) return esc(text);
  const escapedPhrases = signals.map((signal) => signal.phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(escapedPhrases.join("|"), "gi");
  let cursor = 0;
  let html = "";
  for (const match of text.matchAll(pattern)) {
    const signal = signals.find((candidate) => candidate.phrase.toLocaleLowerCase() === match[0].toLocaleLowerCase());
    html += esc(text.slice(cursor, match.index));
    html += `<mark${signal.delta > 0 ? ' class="positive"' : ""}>${esc(match[0])}</mark>`;
    cursor = match.index + match[0].length;
  }
  return html + esc(text.slice(cursor));
}

function documentHtml(content, label, signals) {
  const blocks = content.trim().split(/\n\s*\n/).filter(Boolean);
  const body = blocks.map((block) => {
    const lines = block.split("\n");
    if (lines.every((line) => line.startsWith("- "))) {
      return `<ul>${lines.map((line) => `<li>${highlightedText(line.slice(2), signals)}</li>`).join("")}</ul>`;
    }
    return `<p>${lines.map((line) => highlightedText(line, signals)).join("<br>")}</p>`;
  }).join("");
  return `<h2 class="document-editor-title" contenteditable="false">${esc(label)}</h2>${body}`;
}

function editorDocumentContent() {
  return [...byId("trial-document-editor").children]
    .filter((element) => !element.classList.contains("document-editor-title"))
    .map((element) => element.innerText)
    .join("\n\n")
    .trim();
}

function renderDocumentTabs() {
  byId("document-tabs").innerHTML = Object.entries(trialDocuments).map(([documentId, documentData], index) => `<button class="document-tab${index === 0 ? " is-active" : ""}" type="button" role="tab" aria-selected="${index === 0}" data-document="${esc(documentId)}">${esc(documentData.label)} <span>${documentData.modified ? "Session draft" : "Source metadata"}</span></button>`).join("");
}

async function loadTrialWorkspace() {
  if (state.trialLoaded) return;
  byId("trial-save-status").textContent = "Loading trial data";
  byId("editor-save-state").textContent = "Loading";
  try {
    const response = await fetch(`/trials/${ACTIVE_TRIAL_ID}/documents`);
    if (!response.ok) throw new Error("Trial documents could not be loaded.");
    const workspace = await response.json();
    Object.keys(trialDocuments).forEach((documentId) => delete trialDocuments[documentId]);
    workspace.documents.forEach((documentData) => {
      const signals = signalsForText(documentData.content);
      const signalTotal = signals.reduce((total, signal) => total + signal.delta, 0);
      trialDocuments[documentData.document_id] = {
        label: documentData.label,
        html: documentHtml(documentData.content, documentData.label, signals),
        signals,
        baseScore: Math.max(25, Math.min(85, 60 + signalTotal)),
        modified: documentData.modified
      };
      initializeDocument(trialDocuments[documentData.document_id]);
    });
    state.activeDocument = Object.keys(trialDocuments)[0];
    state.trialLoaded = true;
    byId("trial-workspace-title").textContent = workspace.title;
    byId("trial-workspace-nct").textContent = workspace.nct_id;
    byId("trial-workspace-status").textContent = workspace.overall_status.replaceAll("_", " ");
    byId("trial-source-link").href = workspace.source_url;
    byId("trial-save-status").textContent = "Source metadata loaded";
    byId("editor-save-state").textContent = "Saved";
    renderDocumentTabs();
    renderTrialDocument(state.activeDocument);
  } catch {
    state.trialLoaded = true;
    byId("trial-workspace-title").textContent = "Phase 2 rare disease protocol";
    byId("trial-workspace-status").textContent = "Offline prototype";
    byId("trial-save-status").textContent = "API unavailable; edits stay local";
    byId("editor-save-state").textContent = "Local only";
    renderDocumentTabs();
    renderTrialDocument(state.activeDocument);
  }
}

function showWorkspace(workspace) {
  const showTrial = workspace === "trial";
  byId("overview-view").classList.toggle("hidden", showTrial);
  byId("trial-workspace").classList.toggle("hidden", !showTrial);
  byId("overview-tab").classList.toggle("is-active", !showTrial);
  byId("trial-tab").classList.toggle("is-active", showTrial);
  byId("overview-tab").setAttribute("aria-selected", String(!showTrial));
  byId("trial-tab").setAttribute("aria-selected", String(showTrial));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function openTrialWorkspace() {
  byId("trial-tab-group").classList.remove("hidden");
  showWorkspace("trial");
  await loadTrialWorkspace();
}

function closeTrialWorkspace() {
  showWorkspace("overview");
  byId("trial-tab-group").classList.add("hidden");
}

function renderTrialDocument(documentId) {
  state.activeDocument = documentId;
  const documentData = trialDocuments[documentId];
  byId("trial-document-editor").innerHTML = documentData.html;
  byId("trial-document-editor").setAttribute("aria-label", `${documentData.label} editor`);
  byId("prediction-document-name").textContent = documentData.label;
  document.querySelectorAll(".document-tab").forEach((tab) => {
    const active = tab.dataset.document === documentId;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  updatePrototypePrediction();
}

async function saveTrialDocument(documentId, content) {
  if (documentId === "uploaded") {
    trialDocuments[documentId].modified = true;
    byId("trial-save-status").textContent = "Local changes retained on this device";
    byId("editor-save-state").textContent = "Local only";
    return;
  }
  byId("trial-save-status").textContent = "Saving session draft";
  byId("editor-save-state").textContent = "Saving";
  try {
    const response = await fetch(`/trials/${ACTIVE_TRIAL_ID}/documents/${documentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content })
    });
    if (!response.ok) throw new Error("Draft could not be saved.");
    trialDocuments[documentId].modified = true;
    const tabStatus = document.querySelector(`.document-tab[data-document="${documentId}"] span`);
    if (tabStatus) tabStatus.textContent = "Session draft";
    byId("trial-save-status").textContent = "Session draft saved";
    byId("editor-save-state").textContent = "Saved";
  } catch {
    byId("trial-save-status").textContent = "Save unavailable; edit retained locally";
    byId("editor-save-state").textContent = "Local only";
  }
}

function updatePrototypePrediction() {
  const documentData = trialDocuments[state.activeDocument];
  const editorText = byId("trial-document-editor").innerText.trim();
  const wordCount = editorText.split(/\s+/).filter(Boolean).length;
  const candidateSignals = [...documentData.signals, ...signalCatalog].filter((signal, index, signals) => signals.findIndex((candidate) => candidate.phrase.toLocaleLowerCase() === signal.phrase.toLocaleLowerCase()) === index);
  const detectedSignals = candidateSignals.filter((signal) => editorText.toLocaleLowerCase().includes(signal.phrase.toLocaleLowerCase())).map(signalDescriptor);
  const presentSignals = detectedSignals.filter((signal) => !detectedSignals.some((candidate) => candidate.phrase.length > signal.phrase.length && candidate.phrase.toLocaleLowerCase().includes(signal.phrase.toLocaleLowerCase())));
  const presentSignalTotal = presentSignals.reduce((total, signal) => total + signal.delta, 0);
  const lengthAdjustment = Math.max(-5, Math.min(5, Math.round((wordCount - documentData.initialWordCount) / 5)));
  const score = Math.max(20, Math.min(90, documentData.baseScore + presentSignalTotal - documentData.initialSignalTotal + lengthAdjustment));
  const band = score >= 75 ? "High" : score >= 55 ? "Moderate" : "Low";

  byId("editor-word-count").textContent = `${wordCount} ${wordCount === 1 ? "word" : "words"}`;
  byId("trial-success-score").textContent = `${score}%`;
  byId("trial-success-band").textContent = band;
  byId("trial-success-track").style.width = `${score}%`;
  byId("contribution-count").textContent = `${presentSignals.length} ${presentSignals.length === 1 ? "signal" : "signals"}`;
  byId("prediction-updated-at").textContent = "Just now";
  refreshEditorHighlights(presentSignals);
  documentData.html = byId("trial-document-editor").innerHTML;
  byId("phrase-contributions").innerHTML = presentSignals.length
    ? presentSignals.sort((left, right) => Math.abs(right.delta) - Math.abs(left.delta)).map((signal) => `<article class="phrase-signal ${signal.delta < 0 ? "negative" : "positive"} severity-${signal.severity}"><div class="phrase-signal-heading"><q>${esc(signal.phrase)}</q><span class="signal-score"><small>${signal.severity}</small><strong>${signal.delta > 0 ? "+" : ""}${signal.delta}</strong></span></div><p>${esc(signal.detail)}</p><button class="jump-to-phrase" type="button" data-signal-id="${signal.signalId}" aria-label="Go to phrase: ${esc(signal.phrase)}">Go to phrase <span aria-hidden="true">&#8595;</span></button></article>`).join("")
    : `<article class="phrase-signal negative"><div class="phrase-signal-heading"><q>No tracked phrases found</q><strong>0</strong></div><p>Edit this document to continue testing the explainability panel.</p></article>`;
}

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

async function extractLocalTextFile(file) {
  const extension = file.name.includes(".") ? file.name.split(".").pop().toLocaleLowerCase() : "";
  if (!localTextExtensions.has(extension) && !(file.type.startsWith("text/") && !extension)) return null;
  if (file.size > maxDocumentBytes) throw new Error("The uploaded file exceeds the 25 MB editor limit.");

  const bytes = new Uint8Array(await file.arrayBuffer());
  let text;
  if (bytes[0] === 0xff && bytes[1] === 0xfe) text = new TextDecoder("utf-16le").decode(bytes);
  else if (bytes[0] === 0xfe && bytes[1] === 0xff) text = new TextDecoder("utf-16be").decode(bytes);
  else {
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch {
      text = new TextDecoder("windows-1252").decode(bytes);
    }
  }

  if (extension === "json") {
    try {
      text = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      throw new Error("The JSON file is not valid JSON.");
    }
  } else if (extension === "html" || extension === "htm") {
    const documentRoot = new DOMParser().parseFromString(text, "text/html");
    documentRoot.querySelectorAll("script, style, noscript").forEach((element) => element.remove());
    text = documentRoot.body.textContent;
  }

  text = text.replace(/\r\n?/g, "\n").split("\n").map((line) => line.trimEnd()).join("\n").trim();
  if (!text) throw new Error("No editable text could be extracted from this file.");
  return { text, extractor: extension === "json" ? "JSON" : extension === "html" || extension === "htm" ? "HTML" : extension === "csv" || extension === "tsv" ? "Delimited text" : "Plain text", character_count: text.length };
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

function openUploadedDocument(event) {
  event.preventDefault();
  if (state.documentExtracting) return;
  const content = byId("protocol-text").value.trim();
  if (!content) return;
  const file = byId("protocol-file").files[0];
  const label = file?.name.replace(/\.[^.]+$/, "") || "Uploaded protocol";
  const signals = signalsForText(content);
  const signalTotal = signals.reduce((total, signal) => total + signal.delta, 0);

  Object.keys(trialDocuments).forEach((documentId) => delete trialDocuments[documentId]);
  trialDocuments.uploaded = {
    label,
    html: documentHtml(content, label, signals),
    signals,
    baseScore: Math.max(25, Math.min(85, 60 + signalTotal)),
    modified: true
  };
  initializeDocument(trialDocuments.uploaded);
  state.activeDocument = "uploaded";
  state.trialLoaded = true;
  byId("trial-workspace-title").textContent = label;
  byId("trial-workspace-nct").textContent = byId("anchor-nct").value.trim() || "Local document";
  byId("trial-workspace-status").textContent = "Editor preview";
  byId("trial-source-link").removeAttribute("href");
  byId("trial-source-link").textContent = "Uploaded locally";
  byId("trial-save-status").textContent = "Local document loaded";
  byId("editor-save-state").textContent = "Local only";
  renderDocumentTabs();
  byId("trial-tab-group").classList.remove("hidden");
  showWorkspace("trial");
  renderTrialDocument("uploaded");
  byId("protocol-dialog").close();
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
      const availabilityLabel = device.connected && device.availability === "available" ? "Connected" : "Not connected";
      const identityRow = device.connected
        ? `<dt>Identity</dt><dd>${device.identity_verified ? "CA-verified" : "process allowlisted"}</dd>`
        : "";
      return `<article class="device${device.connected ? "" : " device-expected"}"><h3>${esc(device.name)}</h3><p>${detail}</p><dl><dt>Allowlist</dt><dd>${device.allowlisted ? "Allowed" : "Not allowed"}</dd><dt>Capacity</dt><dd>${capacity}</dd><dt>Availability</dt><dd class="availability ${availabilityLabel.toLowerCase().replaceAll(" ", "-")}">${availabilityLabel}</dd>${identityRow}<dt>Assigned tasks</dt><dd>${device.assigned_tasks.length}</dd></dl></article>`;
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
  byId("compute-mode").textContent = readiness.mode === "two-host-lan-pilot" ? "Two-host LAN pilot" : "Single-host development";
  const notice = byId("compute-readiness-notice");
  const workers = plural(readiness.active_worker_count, "approved worker", "approved workers");
  const hosts = plural(readiness.distinct_active_host_count, "host", "hosts");
  let html;
  if (readiness.production_ready) {
    html = `<strong>Enterprise Deployment Ready</strong> Certificate-backed device identity verified. ${plural(readiness.verified_identity_worker_count, "CA-issued worker", "CA-issued workers")} across ${readiness.distinct_active_host_count} hosts approved. Required production controls are in force.`;
  } else if (readiness.certificate_identity_enforced) {
    html = `<strong>Development Deployment</strong> Certificate-backed device identity is enforced for enrolled workers, but the remaining production controls below are not yet in place:${controlsList(readiness.remaining_production_controls)}`;
  } else {
    html = `<strong>Development Deployment</strong> Certificate-backed device identity is not yet enforced. ${workers} across ${hosts} are currently using process-level allowlisting.${controlsList(readiness.remaining_production_controls)}`;
  }
  if (!readiness.ready) html += `<p class="blocker-copy">Distributed comparison unavailable — ${esc(readiness.blockers.join(" "))} The local text editor remains available on this device.</p>`;
  notice.innerHTML = html;
}

let debounce; byId("protocol-form").addEventListener("input", () => { updateDraftMetrics(); clearTimeout(debounce); debounce = setTimeout(analyzeDraft, 600); });
byId("protocol-form").addEventListener("submit", openUploadedDocument);
byId("compare-toggle").addEventListener("change", (event) => { byId("candidate-b").classList.toggle("hidden", !event.target.checked); updateDraftMetrics(); });
byId("protocol-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const status = byId("file-extraction-status");
  const submit = byId("submit-comparison");
  state.documentExtracting = true;
  submit.disabled = true;
  status.className = "file-extraction-status is-loading";
  status.textContent = `Extracting ${file.name}…`;
  try {
    let result = await extractLocalTextFile(file);
    if (!result) {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch("/documents/extract", { method: "POST", body: formData });
      const responseType = response.headers.get("content-type") || "";
      const payload = responseType.includes("application/json") ? await response.json() : {};
      if (!response.ok) throw new Error(payload.detail || "This file requires the document extraction service, which is unavailable in the hosted desktop app.");
      result = payload;
    }
    byId("protocol-text").value = result.text;
    status.className = "file-extraction-status is-ready";
    status.textContent = `${result.extractor} extracted · ${result.character_count.toLocaleString()} characters`;
    updateDraftMetrics();
    analyzeDraft();
  } catch (error) {
    byId("protocol-text").value = "";
    status.className = "file-extraction-status is-error";
    status.textContent = error.message;
  } finally {
    state.documentExtracting = false;
    submit.disabled = false;
  }
});
byId("open-protocol").addEventListener("click", () => byId("protocol-dialog").showModal());
byId("close-protocol").addEventListener("click", () => byId("protocol-dialog").close());
byId("protocol-dialog").addEventListener("click", (event) => { if (event.target === byId("protocol-dialog")) byId("protocol-dialog").close(); });
byId("devices-button").addEventListener("click", () => byId("devices").scrollIntoView({ behavior: "smooth" }));
byId("analyze-word").addEventListener("click", analyzeWordAssociation);
byId("association-word").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); analyzeWordAssociation(); } });
byId("close-gallery").addEventListener("click", () => { byId("model-gallery").open = false; byId("model-gallery").scrollIntoView({ behavior: "smooth", block: "nearest" }); });
byId("open-trial-workspace").addEventListener("click", openTrialWorkspace);
byId("overview-tab").addEventListener("click", () => showWorkspace("overview"));
byId("trial-tab").addEventListener("click", () => showWorkspace("trial"));
byId("close-trial-tab").addEventListener("click", closeTrialWorkspace);
byId("phrase-contributions").addEventListener("click", (event) => {
  const button = event.target.closest(".jump-to-phrase");
  if (button) jumpToSignal(button.dataset.signalId);
});
byId("document-tabs").addEventListener("click", (event) => {
  const tab = event.target.closest(".document-tab");
  if (!tab || tab.dataset.document === state.activeDocument) return;
  trialDocuments[state.activeDocument].html = byId("trial-document-editor").innerHTML;
  renderTrialDocument(tab.dataset.document);
});
const desktopDownload = document.querySelector(".desktop-download");
const downloadTrigger = desktopDownload.querySelector(".download-trigger");
function setDownloadMenu(open) {
  desktopDownload.classList.toggle("is-open", open);
  downloadTrigger.setAttribute("aria-expanded", String(open));
}
downloadTrigger.addEventListener("click", () => setDownloadMenu(!desktopDownload.classList.contains("is-open")));
document.addEventListener("click", (event) => {
  if (!desktopDownload.contains(event.target)) setDownloadMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setDownloadMenu(false);
    downloadTrigger.focus();
  }
});
document.querySelectorAll("[data-command]").forEach((button) => {
  button.addEventListener("mousedown", (event) => event.preventDefault());
  button.addEventListener("click", () => {
    byId("trial-document-editor").focus();
    document.execCommand(button.dataset.command, false);
  });
});
let predictionDebounce;
let saveDebounce;
byId("trial-document-editor").addEventListener("input", () => {
  const documentId = state.activeDocument;
  const content = editorDocumentContent();
  trialDocuments[documentId].html = byId("trial-document-editor").innerHTML;
  byId("trial-save-status").textContent = "Unsaved local changes";
  byId("editor-save-state").textContent = "Unsaved";
  clearTimeout(predictionDebounce);
  predictionDebounce = setTimeout(updatePrototypePrediction, 180);
  clearTimeout(saveDebounce);
  saveDebounce = setTimeout(() => saveTrialDocument(documentId, content), 700);
});
byId("trial-document-editor").addEventListener("paste", (event) => {
  event.preventDefault();
  document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
});
function initializeDashboard() {
  updateDraftMetrics();
  analyzeDraft();
  loadDevices();
  loadJobs();
  loadComputeReadiness();
  setInterval(loadComputeReadiness, 5000);
  setInterval(loadDevices, 3000);
}

window.onBiostonkAuthenticated = initializeDashboard;