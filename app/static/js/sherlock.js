const sh = {
  form: document.querySelector("#sherlockForm"),
  document: document.querySelector("#sherlockDocument"),
  queryBtn: document.querySelector("#sherlockQueryBtn"),
  validateBtn: document.querySelector("#validateCpfBtn"),
  simulateBtn: document.querySelector("#simulateCpfBtn"),
  message: document.querySelector("#sherlockMessage"),
  resultSection: document.querySelector("#sherlockResultSection"),
  result: document.querySelector("#sherlockResult"),
  resultSummary: document.querySelector("#resultSummary"),
  history: document.querySelector("#sherlockHistory"),
  clearHistory: document.querySelector("#clearSherlockHistory"),
  topStatus: document.querySelector("#sherlockTopStatus"),
  cpfRealStatus: document.querySelector("#cpfRealStatus"),
  cpfLabStatus: document.querySelector("#cpfLabStatus"),
  cnpjProviderStatus: document.querySelector("#cnpjProviderStatus"),
  cacheStatus: document.querySelector("#cacheStatus"),
};

const HISTORY_KEY = "agente_fino_sherlock_history";
const nativeFetch = window.fetch.bind(window);
let csrfToken = null;

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
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
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

function onlyDigits(value) {
  return String(value || "").replace(/\D/g, "");
}

function setLoading(active, label = "Consultar") {
  sh.queryBtn.disabled = active;
  sh.validateBtn.disabled = active;
  sh.simulateBtn.disabled = active;
  sh.queryBtn.textContent = active ? "Consultando" : label;
  sh.queryBtn.classList.toggle("loading", active);
}

function showMessage(message, isError = false) {
  sh.message.textContent = message || "";
  sh.message.style.color = isError ? "#b80012" : "#6b7280";
}

function renderResult(data) {
  sh.resultSection.hidden = false;
  sh.resultSummary.textContent = `${data.status || "ok"} - ${data.latency_ms || 0} ms`;
  const fields = Object.entries(data.data || {}).filter(([, value]) => !["", null, undefined].includes(value));
  sh.result.innerHTML = `
    <div class="result-answer">${escapeHtml(data.answer || "Consulta concluida.")}</div>
    ${fields.map(([key, value]) => `
      <div class="result-item">
        <span>${escapeHtml(key.replaceAll("_", " "))}</span>
        <strong>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : value)}</strong>
      </div>
    `).join("")}
  `;
}

function readHistory() {
  try {
    const rows = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(rows) ? rows.slice(0, 50) : [];
  } catch {
    return [];
  }
}

function saveHistory(data) {
  const row = {
    document: data.document || "***",
    intent: data.intent || "sherlock_query",
    status: data.status || "error",
    created_at: new Date().toLocaleString("pt-BR"),
  };
  const rows = [row, ...readHistory()].slice(0, 50);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(rows));
  renderHistory();
}

function renderHistory() {
  const rows = readHistory();
  sh.history.innerHTML = rows.length
    ? rows.map((row) => `
      <article class="history-item">
        <div>
          <strong>${escapeHtml(row.document)}</strong>
          <small>${escapeHtml(row.created_at)} - ${escapeHtml(row.intent)}</small>
        </div>
        <span class="sherlock-status-pill">${escapeHtml(row.status)}</span>
      </article>
    `).join("")
    : `<article class="history-item"><small>Nenhuma consulta registrada neste navegador.</small></article>`;
}

async function callSherlock(endpoint) {
  const document = onlyDigits(sh.document.value);
  if (![11, 14].includes(document.length)) {
    showMessage("Informe um CPF com 11 digitos ou CNPJ com 14 digitos.", true);
    sh.document.focus();
    return;
  }
  setLoading(true);
  showMessage("Processando com seguranca...");
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ document }),
    });
    const data = await response.json().catch(() => ({ status: "error", answer: "Resposta invalida do servidor." }));
    renderResult(data);
    saveHistory(data);
    showMessage(data.status === "ok" ? "Consulta concluida." : data.answer, data.status !== "ok");
  } catch (error) {
    showMessage(error.message || "Nao foi possivel consultar agora.", true);
  } finally {
    setLoading(false);
  }
}

async function loadStatus() {
  try {
    const response = await fetch("/api/sherlock/status");
    const data = await response.json();
    sh.topStatus.textContent = data.active ? "Sherlock ativo" : "Sherlock inativo";
    sh.cpfRealStatus.textContent = data.cpf_real || "--";
    sh.cpfLabStatus.textContent = data.cpf_lab || "--";
    sh.cnpjProviderStatus.textContent = data.cnpj_provider || "--";
    sh.cacheStatus.textContent = data.redis_cache === "ativo" ? "redis" : data.cache_backend || "memory";
  } catch {
    sh.topStatus.textContent = "Status indisponivel";
  }
}

sh.form?.addEventListener("submit", (event) => {
  event.preventDefault();
  callSherlock("/api/sherlock/query");
});
sh.validateBtn?.addEventListener("click", () => callSherlock("/api/sherlock/validate-cpf"));
sh.simulateBtn?.addEventListener("click", () => callSherlock("/api/sherlock/simulate-cpf"));
sh.clearHistory?.addEventListener("click", () => {
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
});

renderHistory();
loadStatus();
sh.document?.focus();
