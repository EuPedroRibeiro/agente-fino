const df = {
  gate: document.querySelector("#darkforestGate"),
  gateCheck: document.querySelector("#darkforestGateCheck"),
  continueBtn: document.querySelector("#darkforestContinueBtn"),
  form: document.querySelector("#darkforestForm"),
  target: document.querySelector("#darkforestTarget"),
  authorization: document.querySelector("#darkforestAuthorization"),
  scanBtn: document.querySelector("#darkforestScanBtn"),
  steps: Array.from(document.querySelectorAll("#darkforestSteps li")),
  status: document.querySelector("#darkforestStatus"),
  results: document.querySelector("#darkforestResults"),
  summary: document.querySelector("#darkforestSummary"),
  history: document.querySelector("#darkforestHistory"),
  refreshHistory: document.querySelector("#darkforestRefreshHistory"),
};

let acceptedNotice = sessionStorage.getItem("darkforest_sensitive_notice") === "true";
let csrfToken = null;
const nativeFetch = window.fetch.bind(window);

async function ensureCsrfToken() {
  if (csrfToken) return csrfToken;
  const response = await nativeFetch("/api/auth/csrf");
  if (!response.ok) throw new Error("Falha ao preparar sessao segura.");
  const data = await response.json();
  csrfToken = data.csrf_token;
  return csrfToken;
}

window.fetch = async (input, options = {}) => {
  const method = String(options.method || "GET").toUpperCase();
  if (["POST", "PATCH", "DELETE", "PUT"].includes(method)) {
    const headers = new Headers(options.headers || {});
    if (!headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", await ensureCsrfToken());
    options = { ...options, headers };
  }
  return nativeFetch(input, options);
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setGateState() {
  if (df.gate) df.gate.classList.toggle("hidden", acceptedNotice);
  if (df.continueBtn) df.continueBtn.disabled = !df.gateCheck?.checked;
}

function setStep(index) {
  df.steps.forEach((step, stepIndex) => {
    step.classList.toggle("active", stepIndex === index);
    step.classList.toggle("done", stepIndex < index);
  });
}

function setStatus(text) {
  if (df.status) df.status.textContent = text;
}

function renderReport(report) {
  if (df.summary) {
    df.summary.textContent = `${report.findings_count || 0} achado(s) - risco ${report.risk_level || "low"} - ${report.latency_ms || 0} ms`;
  }
  if (!df.results) return;
  const findings = report.findings || [];
  if (!findings.length) {
    df.results.innerHTML = `
      <article class="finding-card">
        <h3>Nenhum segredo encontrado</h3>
        <div class="finding-meta">
          <span>Arquivos analisados: ${escapeHtml(report.scanned_files || 0)}</span>
          <span>Ignorados: ${escapeHtml(report.skipped_files || 0)}</span>
          <span>${escapeHtml(report.recommendation || "")}</span>
        </div>
      </article>
    `;
    return;
  }
  df.results.innerHTML = findings
    .map((finding) => `
      <article class="finding-card ${escapeHtml(finding.risk)}">
        <span class="risk-badge">${escapeHtml(finding.risk)}</span>
        <h3>${escapeHtml(finding.type)}</h3>
        <div class="finding-meta">
          <span>Origem: ${escapeHtml(finding.source)}${finding.line ? ` - linha ${escapeHtml(finding.line)}` : ""}</span>
          <span>Trecho mascarado:</span>
          <code class="masked-secret">${escapeHtml(finding.masked_value)}</code>
          <span>Recomendacao: ${escapeHtml(finding.recommendation)}</span>
          <span>Data/hora: ${escapeHtml(report.generated_at)}</span>
        </div>
      </article>
    `)
    .join("");
}

function renderHistory(rows) {
  if (!df.history) return;
  if (!rows.length) {
    df.history.innerHTML = `<div class="history-item"><span>Nenhuma analise registrada ainda.</span></div>`;
    return;
  }
  df.history.innerHTML = rows
    .map((row) => `
      <article class="history-item">
        <div>
          <strong>${escapeHtml(row.target || "alvo")}</strong>
          <small>${escapeHtml(row.created_at || "")} - ${escapeHtml(row.status || "")}</small>
        </div>
        <span class="risk-badge">${escapeHtml(row.risk_level || "low")} - ${escapeHtml(row.findings_count || 0)}</span>
      </article>
    `)
    .join("");
}

async function loadHistory() {
  const response = await fetch("/api/security/darkforest/history");
  if (!response.ok) return;
  const data = await response.json();
  renderHistory(data.history || []);
}

async function runScan(event) {
  event.preventDefault();
  if (!acceptedNotice) {
    setGateState();
    return;
  }
  if (!df.authorization?.checked) {
    setStatus("Marque a confirmacao de autorizacao.");
    return;
  }
  const target = (df.target?.value || "").trim();
  if (!target) {
    setStatus("Informe um alvo autorizado.");
    df.target?.focus();
    return;
  }
  df.scanBtn.disabled = true;
  setStep(0);
  setStatus("Preparando analise...");
  const intervals = [
    setTimeout(() => { setStep(1); setStatus("Buscando possiveis credenciais..."); }, 350),
    setTimeout(() => { setStep(2); setStatus("Validando padroes encontrados..."); }, 850),
    setTimeout(() => { setStep(3); setStatus("Gerando relatorio..."); }, 1300),
  ];
  try {
    const response = await fetch("/api/security/darkforest/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({
        target,
        accepted_notice: true,
        confirmed_authorization: true,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Falha na analise.");
    setStep(4);
    setStatus("Analise concluida.");
    renderReport(data);
    await loadHistory();
  } catch (error) {
    setStatus(error.message || "Erro na analise.");
  } finally {
    intervals.forEach(clearTimeout);
    df.scanBtn.disabled = false;
  }
}

df.gateCheck?.addEventListener("change", setGateState);
df.continueBtn?.addEventListener("click", () => {
  if (!df.gateCheck?.checked) return;
  acceptedNotice = true;
  sessionStorage.setItem("darkforest_sensitive_notice", "true");
  if (df.authorization) df.authorization.checked = true;
  setGateState();
  df.target?.focus();
});
df.form?.addEventListener("submit", runScan);
df.refreshHistory?.addEventListener("click", () => loadHistory());

setGateState();
loadHistory().catch(() => {});

