const elements = {
  connectionStatus: document.querySelector("#connectionStatus"),
  cpuPercent: document.querySelector("#cpuPercent"),
  ramPercent: document.querySelector("#ramPercent"),
  diskPercent: document.querySelector("#diskPercent"),
  cpuMeter: document.querySelector("#cpuMeter"),
  ramMeter: document.querySelector("#ramMeter"),
  diskMeter: document.querySelector("#diskMeter"),
  hostname: document.querySelector("#hostname"),
  osName: document.querySelector("#osName"),
  localIp: document.querySelector("#localIp"),
  uptime: document.querySelector("#uptime"),
  bootTime: document.querySelector("#bootTime"),
  reportBtn: document.querySelector("#reportBtn"),
  copyReportBtn: document.querySelector("#copyReportBtn"),
  downloadReportBtn: document.querySelector("#downloadReportBtn"),
  cleanBtn: document.querySelector("#cleanBtn"),
  spoolerBtn: document.querySelector("#spoolerBtn"),
  refreshLogsBtn: document.querySelector("#refreshLogsBtn"),
  openAgentBtn: document.querySelector("#openAgentBtn"),
  logoutBtn: document.querySelector("#logoutBtn"),
  actionOutput: document.querySelector("#actionOutput"),
  logsList: document.querySelector("#logsList"),
};

let lastReport = null;
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
  const url = typeof input === "string" ? input : input?.url || "";
  const method = String(options.method || "GET").toUpperCase();
  const unsafe = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  if (unsafe && !url.includes("/api/auth/login") && !url.includes("/api/auth/csrf")) {
    const headers = new Headers(options.headers || {});
    if (!headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", await ensureCsrfToken());
    }
    options = { ...options, headers };
  }
  return nativeFetch(input, options);
};

function requireLocalAuth() {
  const authenticated =
    localStorage.getItem("agente_fino_authenticated") === "true" ||
    localStorage.getItem("nexus_authenticated") === "true";
  if (!authenticated) {
    window.location.replace("/login");
  }
}

function logout() {
  fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  localStorage.removeItem("agente_fino_authenticated");
  localStorage.removeItem("nexus_authenticated");
  window.location.href = "/login";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function percent(value) {
  const parsed = Number(value || 0);
  return Math.max(0, Math.min(100, parsed));
}

function updateMeter(node, value) {
  node.style.width = `${percent(value)}%`;
}

function renderStatus(data) {
  elements.connectionStatus.textContent = data.status || "online";
  elements.cpuPercent.textContent = `${percent(data.cpu?.percent).toFixed(1)}%`;
  elements.ramPercent.textContent = `${percent(data.memory?.percent).toFixed(1)}%`;
  elements.diskPercent.textContent = `${percent(data.disk?.percent).toFixed(1)}%`;
  updateMeter(elements.cpuMeter, data.cpu?.percent);
  updateMeter(elements.ramMeter, data.memory?.percent);
  updateMeter(elements.diskMeter, data.disk?.percent);
  elements.hostname.textContent = data.hostname || "--";
  elements.osName.textContent = data.os || "--";
  elements.localIp.textContent = data.local_ip || "nao detectado";
  elements.uptime.textContent = data.uptime || "--";
  elements.bootTime.textContent = data.boot_time || "--";
}

async function fetchStatus() {
  const response = await fetch("/api/status");
  if (!response.ok) throw new Error("Falha ao consultar status.");
  renderStatus(await response.json());
}

function renderLogs(logs) {
  if (!logs.length) {
    elements.logsList.innerHTML = '<p class="empty-state">Nenhuma acao registrada ainda.</p>';
    return;
  }

  elements.logsList.innerHTML = logs
    .map((log) => {
      const safeStatus = String(log.status || "unknown");
      const adminLabel = log.requires_admin ? '<span class="log-admin">admin</span>' : "";
      const technicalError = log.technical_error
        ? `<span class="log-error-detail">${escapeHtml(log.technical_error)}</span>`
        : "";
      return `
        <article class="log-item">
          <div class="log-main">
            <span class="log-action">${escapeHtml(log.action_name || "--")}</span>
            <span class="log-message">${escapeHtml(log.message || "")}</span>
            ${technicalError}
          </div>
          <div class="log-meta">
            <span class="log-status ${escapeHtml(safeStatus)}">${escapeHtml(safeStatus)}</span>
            ${adminLabel}
          </div>
          <span class="log-time">${escapeHtml(log.timestamp || log.created_at || "--")}</span>
        </article>
      `;
    })
    .join("");
}

async function fetchLogs() {
  const response = await fetch("/api/logs?limit=10");
  if (!response.ok) throw new Error("Falha ao consultar logs.");
  const data = await response.json();
  renderLogs(data.logs || []);
}

async function postAction(url, button, waitingText) {
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = waitingText;

  try {
    let response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ confirm: false }),
    });
    let data = await response.json();
    if (data.requires_confirmation) {
      const accepted = window.confirm(data.message || "Confirmar execucao da acao?");
      if (!accepted) {
        elements.actionOutput.textContent = "Acao cancelada pelo usuario.";
        return;
      }
      response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ confirm: true }),
      });
      data = await response.json();
    }
    lastReport = null;
    updateReportButtons();
    elements.actionOutput.textContent = JSON.stringify(data, null, 2);
    await fetchLogs();
  } catch (error) {
    elements.actionOutput.textContent = error.message;
  } finally {
    button.textContent = originalText;
    button.disabled = false;
  }
}

async function generateReport() {
  elements.reportBtn.disabled = true;
  const originalText = elements.reportBtn.textContent;
  elements.reportBtn.textContent = "Gerando...";

  try {
    const response = await fetch("/api/report");
    const data = await response.json();
    lastReport = data;
    updateReportButtons();
    elements.actionOutput.textContent = JSON.stringify(data, null, 2);
    await fetchLogs();
  } catch (error) {
    elements.actionOutput.textContent = error.message;
  } finally {
    elements.reportBtn.textContent = originalText;
    elements.reportBtn.disabled = false;
  }
}

function updateReportButtons() {
  const enabled = Boolean(lastReport);
  elements.copyReportBtn.disabled = !enabled;
  elements.downloadReportBtn.disabled = !enabled;
}

async function copyReport() {
  if (!lastReport) return;
  const content = JSON.stringify(lastReport, null, 2);
  await navigator.clipboard.writeText(content);
  const originalText = elements.copyReportBtn.textContent;
  elements.copyReportBtn.textContent = "Copiado";
  setTimeout(() => {
    elements.copyReportBtn.textContent = originalText;
  }, 1400);
}

function downloadReport() {
  if (!lastReport) return;
  const content = JSON.stringify(lastReport, null, 2);
  const blob = new Blob([content], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replaceAll(":", "-").replace(".", "-");
  link.href = url;
  link.download = `nexusti-ai-report-${timestamp}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function connectStatusSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws/status`);

  socket.addEventListener("message", (event) => {
    renderStatus(JSON.parse(event.data));
  });

  socket.addEventListener("close", () => {
    elements.connectionStatus.textContent = "reconectando";
    setTimeout(connectStatusSocket, 2500);
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

elements.reportBtn.addEventListener("click", generateReport);
elements.copyReportBtn.addEventListener("click", () => {
  copyReport().catch((error) => {
    elements.actionOutput.textContent = error.message;
  });
});
elements.downloadReportBtn.addEventListener("click", downloadReport);
elements.cleanBtn.addEventListener("click", () => postAction("/api/actions/clean-temp", elements.cleanBtn, "Limpando..."));
elements.spoolerBtn.addEventListener("click", () => postAction("/api/actions/restart-spooler", elements.spoolerBtn, "Reiniciando..."));
elements.refreshLogsBtn.addEventListener("click", fetchLogs);
elements.openAgentBtn?.addEventListener("click", () => {
  window.location.href = "/agent";
});
elements.logoutBtn?.addEventListener("click", logout);

requireLocalAuth();
fetchStatus().catch(() => {
  elements.connectionStatus.textContent = "offline";
});
fetchLogs().catch(() => {
  elements.logsList.innerHTML = '<p class="empty-state">Nao foi possivel carregar os logs.</p>';
});
connectStatusSocket();
