const redlab = {
  labs: [],
  selectedLab: null,
  runId: null,
  csrf: "",
  status: null,
};

const byId = (id) => document.getElementById(id);
const dom = Object.fromEntries([
  "rankName", "xpFill", "xpTotal", "sandboxPanel", "targetPanel", "labList", "missionEmpty", "missionContent",
  "missionCategory", "missionTitle", "missionDifficulty", "missionDescription", "missionObjectives", "missionHints",
  "payloadInput", "startLabBtn", "validateLabBtn", "patchLabBtn", "reportLabBtn", "arenaConsole", "evidenceText",
  "targetStatus", "targetUrl", "techniqueList", "targetConfirmed", "targetScanBtn", "targetResults", "refreshHistoryBtn", "runHistory",
].map((id) => [id, byId(id)]));

const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#039;",
}[char]));

async function csrfToken() {
  if (redlab.csrf) return redlab.csrf;
  const response = await fetch("/api/auth/csrf", { credentials: "same-origin" });
  const data = await response.json();
  redlab.csrf = data.csrf_token || data.token || "";
  return redlab.csrf;
}

async function api(url, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers["X-CSRF-Token"] = await csrfToken();
  const response = await fetch(url, { credentials: "same-origin", ...options, headers });
  const data = await response.json().catch(() => ({ message: "Resposta invalida do servidor." }));
  if (!response.ok) throw new Error(data.message || data.detail || "Operacao indisponivel.");
  return data;
}

function log(message, type = "info") {
  const row = document.createElement("p");
  row.dataset.type = type;
  row.textContent = `[${new Date().toLocaleTimeString("pt-BR")}] ${message}`;
  dom.arenaConsole.appendChild(row);
  dom.arenaConsole.scrollTop = dom.arenaConsole.scrollHeight;
}

function updateProgress(progress = {}) {
  dom.rankName.textContent = progress.rank || "Recruta";
  dom.xpTotal.textContent = `${progress.total_xp || 0} XP`;
  dom.xpFill.style.width = `${progress.percent || 0}%`;
}

function renderLabs() {
  dom.labList.innerHTML = redlab.labs.map((lab) => `
    <button class="lab-card ${redlab.selectedLab?.id === lab.id ? "active" : ""}" type="button" data-lab="${escapeHtml(lab.id)}">
      <small>${escapeHtml(lab.category)} / ${escapeHtml(lab.difficulty)}</small>
      <strong>${escapeHtml(lab.title)}</strong>
      <em>${lab.xp_reward} XP</em>
    </button>`).join("");
}

function selectLab(id) {
  redlab.selectedLab = redlab.labs.find((lab) => lab.id === id) || null;
  redlab.runId = null;
  renderLabs();
  if (!redlab.selectedLab) return;
  const lab = redlab.selectedLab;
  dom.missionEmpty.hidden = true;
  dom.missionContent.hidden = false;
  dom.missionCategory.textContent = lab.category;
  dom.missionTitle.textContent = lab.title;
  dom.missionDifficulty.textContent = lab.difficulty;
  dom.missionDescription.textContent = lab.description;
  dom.missionObjectives.innerHTML = lab.objectives.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  dom.missionHints.innerHTML = lab.hints.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  dom.payloadInput.value = "";
  dom.validateLabBtn.disabled = true;
  dom.patchLabBtn.disabled = true;
  dom.reportLabBtn.disabled = true;
  dom.evidenceText.textContent = "Nenhuma evidencia coletada.";
  log(`Missao selecionada: ${lab.title}`);
}

async function startLab() {
  if (!redlab.selectedLab) return;
  const data = await api("/api/redlab/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lab_id: redlab.selectedLab.id, mode: "sandbox" }),
  });
  redlab.runId = data.run.id;
  dom.validateLabBtn.disabled = false;
  dom.reportLabBtn.disabled = false;
  updateProgress(data.progress);
  log(`Run iniciada: ${redlab.runId}`, "success");
}

async function validateLab() {
  if (!redlab.runId || !redlab.selectedLab) return;
  const data = await api("/api/redlab/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: redlab.runId, lab_id: redlab.selectedLab.id, payload: dom.payloadInput.value }),
  });
  const result = data.result;
  dom.evidenceText.textContent = `${result.evidence} ${result.response_summary}`;
  dom.patchLabBtn.disabled = !result.vulnerability_found;
  updateProgress(data.progress);
  log(
    result.vulnerability_found ? `Vulnerabilidade simulada encontrada. +${result.xp_earned} XP` : "O teste nao concluiu a missao.",
    result.vulnerability_found ? "success" : "info",
  );
  loadHistory();
}

async function patchLab() {
  const data = await api("/api/redlab/patch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: redlab.runId, lab_id: redlab.selectedLab.id }),
  });
  dom.evidenceText.textContent = `${data.patch.patch_diff}\nTestes: ${data.patch.tests_passed}/${data.patch.tests_total}`;
  updateProgress(data.progress);
  log("Patch aplicado e regressoes validadas.", "success");
}

async function loadReport() {
  const data = await api(`/api/redlab/report?run_id=${encodeURIComponent(redlab.runId)}`);
  dom.evidenceText.textContent = JSON.stringify(data, null, 2);
  log("Relatorio da run gerado.", "success");
}

async function loadHistory() {
  const data = await api("/api/redlab/history?limit=12");
  dom.runHistory.innerHTML = data.history.length ? data.history.map((run) => `
    <article class="history-row"><div><strong>${escapeHtml(run.lab_id)}</strong><p>${escapeHtml(run.status)} / ${escapeHtml(run.mode)}</p></div><span>${run.xp_earned || 0} XP</span></article>`).join("") : '<p class="muted">Nenhuma run ainda.</p>';
}

function renderTargetStatus() {
  const target = redlab.status?.target || {};
  dom.targetStatus.textContent = target.enabled ? "allowlist ativa" : "desativado";
  dom.targetScanBtn.disabled = !target.enabled;
  dom.techniqueList.innerHTML = (target.techniques || []).map((technique) => `<label><input type="checkbox" value="${escapeHtml(technique)}" checked /><span>${escapeHtml(technique)}</span></label>`).join("");
}

async function targetScan() {
  const techniques = Array.from(dom.techniqueList.querySelectorAll("input:checked")).map((item) => item.value);
  const data = await api("/api/redlab/target/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: dom.targetUrl.value, techniques, confirmed: dom.targetConfirmed.checked }),
  });
  dom.targetResults.innerHTML = data.results.map((result) => `<article class="target-result"><strong>${escapeHtml(result.technique)} / ${escapeHtml(result.status)}</strong><p>${escapeHtml(result.evidence)}</p><p>${escapeHtml(result.recommendation)}</p></article>`).join("");
  log(`Target preflight concluido: ${data.results.length} categorias.`, "success");
  loadHistory();
}

document.querySelectorAll("[data-mode-tab]").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll("[data-mode-tab]").forEach((item) => item.classList.toggle("active", item === button));
  dom.sandboxPanel.hidden = button.dataset.modeTab !== "sandbox";
  dom.targetPanel.hidden = button.dataset.modeTab !== "target";
}));

dom.labList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-lab]");
  if (button) selectLab(button.dataset.lab);
});
dom.startLabBtn.addEventListener("click", () => startLab().catch((error) => log(error.message, "error")));
dom.validateLabBtn.addEventListener("click", () => validateLab().catch((error) => log(error.message, "error")));
dom.patchLabBtn.addEventListener("click", () => patchLab().catch((error) => log(error.message, "error")));
dom.reportLabBtn.addEventListener("click", () => loadReport().catch((error) => log(error.message, "error")));
dom.targetScanBtn.addEventListener("click", () => targetScan().catch((error) => log(error.message, "error")));
dom.refreshHistoryBtn.addEventListener("click", () => loadHistory().catch((error) => log(error.message, "error")));

Promise.all([api("/api/redlab/status"), api("/api/redlab/labs"), api("/api/redlab/progress")]).then(([status, labs, progress]) => {
  redlab.status = status;
  redlab.labs = labs.labs || [];
  renderLabs();
  renderTargetStatus();
  updateProgress(progress);
  loadHistory();
}).catch((error) => log(error.message, "error"));
