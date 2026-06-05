const ui = {
  chatHistory: document.querySelector("#chatHistory"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendBtn: document.querySelector("#sendBtn"),
  useWebToggle: document.querySelector("#useWebToggle"),
  pcContextToggle: document.querySelector("#pcContextToggle"),
  analyzePcBtn: document.querySelector("#analyzePcBtn"),
  deepResearchBtn: document.querySelector("#deepResearchBtn"),
  darkforestBtn: document.querySelector("#darkforestBtn"),
  securityShortcutBtn: document.querySelector("#securityShortcutBtn"),
  mcpBrasilBtn: document.querySelector("#mcpBrasilBtn"),
  retestGeminiBtn: document.querySelector("#retestGeminiBtn"),
  personalityBtn: document.querySelector("#personalityBtn"),
  memoryBtn: document.querySelector("#memoryBtn"),
  logsBtn: document.querySelector("#logsBtn"),
  matrixBtn: document.querySelector("#matrixBtn"),
  detailsBtn: document.querySelector("#detailsBtn"),
  logoutBtn: document.querySelector("#logoutBtn"),
  toolsBtn: document.querySelector("#toolsBtn"),
  toolsMenu: document.querySelector("#toolsMenu"),
  detailsDrawer: document.querySelector("#detailsDrawer"),
  closeDetailsBtn: document.querySelector("#closeDetailsBtn"),
  newConversationBtn: document.querySelector("#newConversationBtn"),
  conversationSearch: document.querySelector("#conversationSearch"),
  conversationList: document.querySelector("#conversationList"),
  emptyState: document.querySelector("#emptyState"),
  webStatus: document.querySelector("#webStatus"),
  modelStatus: document.querySelector("#modelStatus"),
  geminiStatus: document.querySelector("#geminiStatus"),
  ollamaStatus: document.querySelector("#ollamaStatus"),
  ragStatus: document.querySelector("#ragStatus"),
  memoryStatus: document.querySelector("#memoryStatus"),
  securityStatus: document.querySelector("#securityStatus"),
  publicDataStatus: document.querySelector("#publicDataStatus"),
  mcpBrasilStatus: document.querySelector("#mcpBrasilStatus"),
  providerNarrative: document.querySelector("#providerNarrative"),
  catalogBox: document.querySelector("#catalogBox"),
  latencyHint: document.querySelector("#latencyHint"),
  activityIndicator: document.querySelector("#activityIndicator"),
  activityText: document.querySelector("#activityText"),
  activityDetailsBtn: document.querySelector("#activityDetailsBtn"),
  planBox: document.querySelector("#planBox"),
  riskBox: document.querySelector("#riskBox"),
  actionsBox: document.querySelector("#actionsBox"),
  sourcesBox: document.querySelector("#sourcesBox"),
  memoryModal: document.querySelector("#memoryModal"),
  personalityModal: document.querySelector("#personalityModal"),
  memoryForm: document.querySelector("#memoryForm"),
  memoryCategory: document.querySelector("#memoryCategory"),
  memoryKey: document.querySelector("#memoryKey"),
  memoryValue: document.querySelector("#memoryValue"),
  memorySearch: document.querySelector("#memorySearch"),
  memoryList: document.querySelector("#memoryList"),
  personalityForm: document.querySelector("#personalityForm"),
  personalityTone: document.querySelector("#personalityTone"),
  personalityDetail: document.querySelector("#personalityDetail"),
  personalityEmoji: document.querySelector("#personalityEmoji"),
  personalityStyle: document.querySelector("#personalityStyle"),
  personalityPosture: document.querySelector("#personalityPosture"),
  personalityTechnical: document.querySelector("#personalityTechnical"),
  personalityAutoWeb: document.querySelector("#personalityAutoWeb"),
  personalityAutoMemory: document.querySelector("#personalityAutoMemory"),
  resetPersonalityBtn: document.querySelector("#resetPersonalityBtn"),
};

const AUTH_KEY = "agente_fino_authenticated";
const LEGACY_AUTH_KEY = "nexus_authenticated";
const nativeFetch = window.fetch.bind(window);
let conversationId = null;
let sending = false;
let lastResponseMeta = null;
let activityTimer = null;
let activityHideTimer = null;
let activityStartedAt = 0;
let latestActivityText = "Pensando...";
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

function on(element, eventName, handler) {
  if (element) element.addEventListener(eventName, handler);
}

function isAuthenticated() {
  return localStorage.getItem(AUTH_KEY) === "true" || localStorage.getItem(LEGACY_AUTH_KEY) === "true";
}

function requireLocalAuth() {
  if (!isAuthenticated()) {
    window.location.replace("/login");
  }
}

function logout(event) {
  if (event) event.preventDefault();
  fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(LEGACY_AUTH_KEY);
  window.location.href = "/login";
}

function setHasMessages(hasMessages) {
  document.body.classList.toggle("empty-state-active", !hasMessages);
  document.body.classList.toggle("has-messages", hasMessages);
  ui.emptyState?.classList.toggle("hidden", hasMessages);
  updateComposerHeight();
}

function updateComposerHeight() {
  if (!ui.chatForm) return;
  const height = Math.ceil(ui.chatForm.getBoundingClientRect().height || 148);
  document.documentElement.style.setProperty("--composer-height", `${height}px`);
}

function scrollToBottom() {
  if (!ui.chatHistory) return;
  requestAnimationFrame(() => {
    ui.chatHistory.scrollTop = ui.chatHistory.scrollHeight;
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function addMessage(role, text) {
  setHasMessages(true);
  const node = document.createElement("article");
  node.className = `message ${role}`;
  node.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
  ui.chatHistory.appendChild(node);
  scrollToBottom();
  return node;
}

function setSending(isSending) {
  sending = isSending;
  if (ui.sendBtn) {
    ui.sendBtn.disabled = isSending;
    const label = ui.sendBtn.querySelector(".send-label");
    if (label) label.textContent = isSending ? "Pensando" : "Enviar";
  }
  if (ui.messageInput) ui.messageInput.disabled = isSending;
  updateComposerHeight();
}

function autoResizeTextarea() {
  if (!ui.messageInput) return;
  ui.messageInput.style.height = "auto";
  ui.messageInput.style.height = `${Math.min(ui.messageInput.scrollHeight, 180)}px`;
  updateComposerHeight();
}

function beginActivity() {
  activityStartedAt = performance.now();
  latestActivityText = "Pensando...";
  clearTimeout(activityTimer);
  clearTimeout(activityHideTimer);
  if (ui.activityIndicator) ui.activityIndicator.hidden = true;
  activityTimer = setTimeout(() => {
    showActivity(latestActivityText);
  }, 600);
}

function showActivity(text) {
  if (!ui.activityIndicator || !ui.activityText) return;
  ui.activityText.textContent = text || latestActivityText || "Trabalhando...";
  ui.activityIndicator.hidden = false;
}

function updateActivity(text) {
  if (!text) return;
  latestActivityText = text;
  if (ui.activityIndicator && !ui.activityIndicator.hidden) {
    showActivity(text);
  }
}

function finishActivity(elapsedLabel = null) {
  clearTimeout(activityTimer);
  const elapsed = elapsedLabel || formatElapsed(performance.now() - activityStartedAt);
  if (ui.activityIndicator && !ui.activityIndicator.hidden) {
    showActivity(`Trabalhou por ${elapsed}`);
    activityHideTimer = setTimeout(hideActivity, 1600);
  } else {
    hideActivity();
  }
}

function hideActivity() {
  clearTimeout(activityTimer);
  if (ui.activityIndicator) ui.activityIndicator.hidden = true;
}

function formatElapsed(ms) {
  const seconds = Math.max(0, Math.round(ms / 1000));
  if (seconds < 1) return "menos de 1s";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}min ${seconds % 60}s`;
}

function renderResponse(data) {
  conversationId = data.conversation_id || conversationId;
  const meta = {
    provider: data.model_used?.provider || "--",
    model: data.model_used?.model || "--",
    intent: data.intent || "--",
    mode: data.mode || "--",
    latency_ms: data.timings_ms?.total || null,
    tools_used: data.selected_tools || data.tool_calls?.map((tool) => tool.name) || [],
    web_sources_count: data.sources?.length || 0,
    rag_status: data.rag_status?.honest_status || "--",
    verifier: data.verifier_result || null,
  };
  lastResponseMeta = meta;
  addMessage("agent", data.final_answer || data.answer || "Sem resposta.");
  scrollToBottom();
  renderPlan(data.plan);
  renderRisk(data);
  if (ui.actionsBox) ui.actionsBox.innerHTML = renderActions(data);
  renderSources(data.sources || []);
  loadConversations().catch(() => {});
}

function renderPlan(plan) {
  if (!ui.planBox) return;
  if (!plan || !plan.steps?.length) {
    ui.planBox.textContent = "Sem plano nesta resposta.";
    return;
  }
  ui.planBox.innerHTML = plan.steps
    .map((step) => `<div><strong>${escapeHtml(step.title)}</strong><br>${escapeHtml(step.detail)}</div>`)
    .join("<hr>");
}

function renderRisk(data) {
  if (!ui.riskBox) return;
  const model = data.model_used || {};
  const rag = data.rag_status || {};
  const web = data.web_status || {};
  const totalMs = data.timings_ms?.total || "";
  const localMs = data.timings_ms?.local_tool ?? model.local_tool_latency_ms ?? "";
  const tools = data.selected_tools?.length ? data.selected_tools.join(", ") : "--";
  ui.riskBox.innerHTML = `
    <div><span class="badge gold">${escapeHtml(data.risk_level || "--")}</span></div>
    <div>Confianca: ${Math.round(Number(data.confidence || 0) * 100)}%</div>
    <div>Modo: ${escapeHtml(data.mode || "--")}</div>
    <div>Intent: ${escapeHtml(data.intent || "--")}</div>
    <div>Ferramenta: ${escapeHtml(tools)}</div>
    <div>Modelo usado: ${escapeHtml(model.provider || "--")} ${model.model ? `(${escapeHtml(model.model)})` : ""}</div>
    <div>LLM usado: ${model.used_model || model.llm_used ? "sim" : "nao"}</div>
    <div>Prioridade direta: ${model.answer_priority_applied ? "sim" : "nao"}</div>
    ${model.path ? `<div>Caminho: ${escapeHtml(model.path)}</div>` : ""}
    ${model.cache_hit != null ? `<div>Cache: ${model.cache_hit ? "hit" : "miss"}</div>` : ""}
    ${model.timeout != null ? `<div>Timeout: ${model.timeout ? "sim" : "nao"}</div>` : ""}
    ${model.skipped_count != null ? `<div>Ignorados: ${escapeHtml(model.skipped_count)}</div>` : ""}
    <div>RAG: ${escapeHtml(rag.honest_status || "--")} ${rag.chunks ? `- ${escapeHtml(rag.chunks)} chunks` : ""}</div>
    <div>Web fontes: ${escapeHtml(web.sources_read ?? data.sources?.length ?? 0)}</div>
    <div>Ferramenta local: ${escapeHtml(localMs || "--")} ms</div>
    <div>Tempo: ${escapeHtml(totalMs || "--")} ms</div>
  `;
}

function renderActions(data) {
  if (data.tool_calls?.length) {
    return data.tool_calls
      .map((call) => {
        const status = call.status || "--";
        const latency = call.latency_ms != null ? `${call.latency_ms} ms` : "--";
        const extra = call.result?.truncated ? "resultado truncado por seguranca" : "";
        return `<div><strong>${escapeHtml(call.name)}</strong><br>Status: ${escapeHtml(status)} - Tempo: ${escapeHtml(latency)}<br>${escapeHtml(extra)}</div>`;
      })
      .join("<hr>");
  }
  const actions = data.pending_actions?.length ? data.pending_actions : data.safe_actions || [];
  if (!actions.length) return "Sem acoes nesta resposta.";
  return actions
    .map((action) => {
      const actionName = action.action_name || action.tool || "acao";
      const reason = action.reason || action.risk_level || "";
      const confirmButton = action.id
        ? `<button data-action-id="${escapeHtml(action.id)}" class="confirm-action mini-btn" type="button">Confirmar</button>`
        : "";
      return `<div><strong>${escapeHtml(actionName)}</strong><br>${escapeHtml(reason)}<br>${confirmButton}</div>`;
    })
    .join("<hr>");
}

function renderSources(sources) {
  if (!ui.sourcesBox) return;
  if (!sources.length) {
    ui.sourcesBox.textContent = "Sem fontes nesta resposta.";
    return;
  }
  ui.sourcesBox.innerHTML = sources
    .map((source) => `
      <div class="source-item">
        <a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>
        <span class="badge">${escapeHtml(source.reliability)} - ${escapeHtml(source.source_status)}</span>
        <span>${escapeHtml(source.excerpt || "")}</span>
      </div>
    `)
    .join("");
}

async function sendMessage(message = null) {
  const text = (message ?? ui.messageInput.value).trim();
  if (!text || sending) return;
  if (isDarkForestCommand(text)) {
    addMessage("user", text);
    addMessage("agent", "Vou abrir o Scanner de Vazamento de Chaves. A analise so roda depois do aviso sensivel e da sua confirmacao de autorizacao.");
    if (ui.messageInput) ui.messageInput.value = "";
    setTimeout(() => {
      window.location.href = "/security";
    }, 650);
    return;
  }
  setSending(true);
  const started = performance.now();
  addMessage("user", text);
  const pending = addMessage("agent", "Pensando...");
  ui.messageInput.value = "";
  autoResizeTextarea();
  if (ui.latencyHint) ui.latencyHint.textContent = "processando";
  beginActivity();
  const payload = {
    message: text,
    use_web: Boolean(ui.useWebToggle?.checked),
    include_system_context: Boolean(ui.pcContextToggle?.checked),
    mode: "auto",
    conversation_id: conversationId,
  };
  try {
    const data = await runWithActivity(payload).catch(() => postChat(payload));
    pending.remove();
    renderResponse(data);
    if (ui.latencyHint) ui.latencyHint.textContent = `${Math.round(performance.now() - started)} ms`;
    finishActivity(data.activity?.elapsed_label);
  } catch (error) {
    pending.remove();
    hideActivity();
    addMessage("agent", error.message);
    if (ui.latencyHint) ui.latencyHint.textContent = "erro";
  } finally {
    setSending(false);
    ui.messageInput.focus();
  }
}

function isDarkForestCommand(text) {
  const normalized = String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
  return (
    normalized.includes("scanner de vazamento") ||
    normalized.includes("verificar possiveis chaves") ||
    normalized.includes("chaves expostas") ||
    normalized.includes("abrir scanner") ||
    normalized.includes("darkforest")
  );
}

async function postChat(payload) {
  const response = await fetch("/api/agent/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });
  const data = await readJsonResponse(response);
  if (!response.ok) throw new Error(errorMessageFromPayload(data, "Nao foi possivel concluir a mensagem agora."));
  return data;
}

async function runWithActivity(payload) {
  if (!window.EventSource) throw new Error("SSE indisponivel.");
  const response = await fetch("/api/agent/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });
  const data = await readJsonResponse(response);
  if (!response.ok) throw new Error(errorMessageFromPayload(data, "Execucao em streaming indisponivel."));
  if (!data.run_id) throw new Error("Execucao sem identificador.");
  return streamRunEvents(data.run_id);
}

async function readJsonResponse(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

function errorMessageFromPayload(data, fallback) {
  return data?.detail || data?.message || data?.error || fallback;
}

function streamRunEvents(runId) {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/agent/runs/${encodeURIComponent(runId)}/events`);
    let settled = false;
    const timeout = setTimeout(() => finish(new Error("Tempo limite da execucao.")), 120000);

    function finish(value, isSuccess = false) {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      source.close();
      if (isSuccess) resolve(value);
      else reject(value);
    }

    function dataFrom(event) {
      try {
        return JSON.parse(event.data || "{}");
      } catch {
        return {};
      }
    }

    [
      "run_started",
      "route_detected",
      "local_tool_started",
      "local_tool_progress",
      "web_search_started",
      "web_source_found",
      "web_source_opened",
      "web_search_done",
      "rag_started",
      "model_started",
      "verifier_started",
      "finalizing",
    ].forEach((name) => {
      source.addEventListener(name, (event) => {
        const payload = dataFrom(event);
        updateActivity(payload.message);
      });
    });

    source.addEventListener("run_done", (event) => {
      const payload = dataFrom(event);
      finish(payload.response, true);
    });
    source.addEventListener("run_error", (event) => {
      const payload = dataFrom(event);
      finish(new Error(payload.error || "Nao consegui concluir a execucao."));
    });
    source.onerror = () => finish(new Error("Conexao de atividade interrompida."));
  });
}

async function analyzePc() {
  await sendMessage("Analise este PC");
}

async function deepResearch() {
  const query = ui.messageInput.value.trim();
  if (!query) {
    ui.messageInput.focus();
    return;
  }
  addMessage("user", `Pesquisa profunda: ${query}`);
  const pending = addMessage("agent", "Pesquisando e comparando fontes...");
  const response = await fetch("/api/agent/deep-research", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ query, depth: "deep", official_first: true }),
  });
  const data = await response.json();
  pending.remove();
  addMessage("agent", data.summary || "Pesquisa concluida.");
  renderSources(data.sources || []);
}

async function retestGemini() {
  ui.retestGeminiBtn.disabled = true;
  ui.retestGeminiBtn.textContent = "Retestando...";
  try {
    const response = await fetch("/api/agent/providers/gemini/retest", { method: "POST" });
    const data = await response.json();
    updateProviderBadges(data);
    addMessage("agent", `Reteste concluido. Provider selecionado: ${data.selected_provider || "--"}/${data.selected_model || "--"}.`);
  } finally {
    ui.retestGeminiBtn.disabled = false;
    ui.retestGeminiBtn.textContent = "Retestar providers";
  }
}

async function confirmAction(actionId) {
  const response = await fetch("/api/agent/confirm-action", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ pending_action_id: actionId, confirm: true }),
  });
  const data = await response.json();
  addMessage("agent", JSON.stringify(data, null, 2));
}

async function loadStatus() {
  const [agentStatus, providerStatus, securityStatus, publicDataStatus, mcpBrasilStatus] = await Promise.allSettled([
    fetch("/api/agent/status").then((response) => response.json()),
    fetch("/api/agent/providers/status").then((response) => response.json()),
    fetch("/api/security/status").then((response) => response.json()),
    fetch("/api/public-data/status").then((response) => response.json()),
    fetch("/api/mcp-brasil/status").then((response) => response.json()),
  ]);
  if (providerStatus.status === "fulfilled") {
    updateProviderBadges(providerStatus.value);
  } else if (agentStatus.status === "fulfilled") {
    updateProviderBadges(agentStatus.value.provider || {});
  }
  if (agentStatus.status === "fulfilled") {
    const data = agentStatus.value;
    if (ui.webStatus) ui.webStatus.textContent = data.web_enabled ? "ativo" : "inativo";
    if (ui.ragStatus) ui.ragStatus.textContent = data.rag_status?.honest_status || (data.rag_enabled ? "ativo" : "inativo");
    if (ui.memoryStatus) ui.memoryStatus.textContent = data.memory_enabled ? "ativa" : "inativa";
  }
  if (securityStatus.status === "fulfilled" && ui.securityStatus) {
    const sec = securityStatus.value;
    ui.securityStatus.textContent = sec.enabled
      ? `ativa | CSRF ${sec.csrf_enabled ? "on" : "off"} | rate ${sec.rate_limit_enabled ? "on" : "off"}`
      : "inativa";
  }
  if (publicDataStatus.status === "fulfilled" && ui.publicDataStatus) {
    const publicData = publicDataStatus.value;
    ui.publicDataStatus.textContent = publicData.active ? "ativo" : "inativo";
  }
  if (mcpBrasilStatus.status === "fulfilled" && ui.mcpBrasilStatus) {
    const mcp = mcpBrasilStatus.value;
    ui.mcpBrasilStatus.textContent = mcp.running ? "online" : (mcp.available ? "instalado" : "offline");
  }
}

function updateProviderBadges(provider) {
  const selected = provider.selected_provider || provider.selected || "local";
  const selectedModel = provider.selected_model || provider.openai_model || "";
  const geminiStatus = provider.gemini_status || "offline";
  const openaiStatus = provider.openai_status || (provider.openai_available ? "online" : "not_configured");
  if (ui.modelStatus) ui.modelStatus.textContent = `${selected}${selectedModel ? `/${selectedModel}` : ""}`;
  if (ui.geminiStatus) ui.geminiStatus.textContent = `OpenAI: ${openaiStatus} | Gemini: ${geminiStatus}`;
  if (ui.ollamaStatus) ui.ollamaStatus.textContent = provider.ollama_status === "disabled_in_cloud" ? "desativado no cloud" : (provider.ollama_status === "online" ? "online" : "offline");
  if (ui.providerNarrative) {
    ui.providerNarrative.textContent = provider.fallback_reason
      ? `Fallback: ${provider.fallback_reason}`
      : `Provider ativo: ${selected}${selectedModel ? `/${selectedModel}` : ""}.`;
  }
}

async function loadCatalog() {
  const response = await fetch("/api/agent/catalog");
  const data = await response.json();
  const summary = data.summary || {};
  if (!ui.catalogBox) return;
  ui.catalogBox.innerHTML = `
    <div><strong>${escapeHtml(summary.model_providers || 0)}</strong><span>Providers</span></div>
    <div><strong>${escapeHtml(summary.vector_stores || 0)}</strong><span>Bancos/RAG</span></div>
    <div><strong>${escapeHtml(summary.web_search_providers || 0)}</strong><span>Buscas web</span></div>
    <div><strong>${escapeHtml(summary.capabilities || 0)}</strong><span>Capacidades</span></div>
  `;
}

async function loadConversations(query = "") {
  const response = await fetch(`/api/agent/conversations${query ? `?query=${encodeURIComponent(query)}` : ""}`);
  const data = await response.json();
  const conversations = data.conversations || [];
  ui.conversationList.innerHTML = conversations.length
    ? conversations.map(renderConversationItem).join("")
    : `<p class="empty-conversations">Sem conversas ainda.</p>`;
}

function renderConversationItem(item) {
  const active = item.id === conversationId ? " active" : "";
  const count = Number(item.message_count || 0);
  return `
    <div class="conversation-item${active}" data-conversation-id="${escapeHtml(item.id)}">
      <div>
        <strong>${escapeHtml(item.title || "Conversa")}</strong>
        <small>${count} ${count === 1 ? "mensagem" : "mensagens"}</small>
      </div>
      <div class="item-actions">
        <button class="mini-btn rename-conversation" type="button" title="Renomear">...</button>
        <button class="mini-btn delete-conversation" type="button" title="Apagar">x</button>
      </div>
    </div>
  `;
}

async function createConversation() {
  const response = await fetch("/api/agent/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ title: "Nova conversa" }),
  });
  const data = await response.json();
  conversationId = data.id;
  ui.chatHistory.innerHTML = "";
  setHasMessages(false);
  await loadConversations();
  ui.messageInput.focus();
}

async function openConversation(id) {
  conversationId = id;
  const response = await fetch(`/api/agent/conversations/${encodeURIComponent(id)}/messages`);
  const data = await response.json();
  ui.chatHistory.innerHTML = "";
  const messages = data.messages || [];
  setHasMessages(Boolean(messages.length));
  for (const message of messages) {
    addMessage(message.role === "assistant" ? "agent" : "user", message.content);
    if (message.role === "assistant") {
      lastResponseMeta = {
        provider: message.provider,
        model: message.model,
        intent: message.intent,
        latency_ms: message.latency_ms,
        tools_used: message.tools_used || [],
        web_sources_count: message.web_sources_count,
      };
    }
  }
  await loadConversations();
}

async function renameConversation(id) {
  const title = window.prompt("Novo titulo da conversa:");
  if (!title) return;
  await fetch(`/api/agent/conversations/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ title }),
  });
  await loadConversations(ui.conversationSearch.value.trim());
}

async function deleteConversation(id) {
  if (!window.confirm("Apagar esta conversa?")) return;
  await fetch(`/api/agent/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (conversationId === id) {
    conversationId = null;
    ui.chatHistory.innerHTML = "";
    setHasMessages(false);
  }
  await loadConversations(ui.conversationSearch.value.trim());
}

function openModal(modal) {
  if (modal) modal.hidden = false;
}

function closeModal(modalId) {
  const modal = document.querySelector(`#${modalId}`);
  if (modal) modal.hidden = true;
}

function openDetailsDrawer() {
  ui.detailsDrawer.classList.add("open");
  ui.detailsDrawer.setAttribute("aria-hidden", "false");
  loadStatus().catch(() => {});
}

function closeDetailsDrawer() {
  ui.detailsDrawer.classList.remove("open");
  ui.detailsDrawer.setAttribute("aria-hidden", "true");
}

function closeToolsMenu() {
  ui.toolsMenu?.classList.remove("open");
  ui.toolsBtn?.setAttribute("aria-expanded", "false");
}

async function loadMemories(query = "") {
  const response = query
    ? await fetch("/api/agent/memory/search", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ query, limit: 50 }),
      })
    : await fetch("/api/agent/memory");
  const data = await response.json();
  const memories = data.memory || data.results || [];
  ui.memoryList.innerHTML = memories.length ? memories.map(renderMemoryItem).join("") : "Nenhuma memoria salva ainda.";
}

function renderMemoryItem(memory) {
  const id = memory.id;
  const key = memory.key || memory.title || "memoria";
  const value = memory.value || memory.content || "";
  return `
    <div class="memory-item" data-memory-id="${escapeHtml(id)}">
      <strong>${escapeHtml(key)}</strong>
      <div><span class="badge">${escapeHtml(memory.category || memory.memory_type || "--")}</span> ${memory.pinned ? '<span class="badge gold">fixada</span>' : ""}</div>
      <p>${escapeHtml(value)}</p>
      <div class="memory-actions">
        <button class="mini-btn edit-memory" type="button">editar</button>
        <button class="mini-btn pin-memory" type="button">${memory.pinned ? "desfixar" : "fixar"}</button>
        <button class="mini-btn archive-memory" type="button">arquivar</button>
        <button class="mini-btn delete-memory" type="button">apagar</button>
      </div>
    </div>
  `;
}

async function saveMemory(event) {
  event.preventDefault();
  const value = ui.memoryValue.value.trim();
  if (!value) return;
  await fetch("/api/agent/memory", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({
      category: ui.memoryCategory.value,
      key: ui.memoryKey.value.trim() || null,
      value,
      source: "user",
      confidence: 0.95,
      pinned: false,
    }),
  });
  ui.memoryValue.value = "";
  ui.memoryKey.value = "";
  await loadMemories(ui.memorySearch.value.trim());
}

async function handleMemoryAction(event) {
  const item = event.target.closest("[data-memory-id]");
  if (!item) return;
  const id = item.dataset.memoryId;
  if (event.target.matches(".delete-memory")) {
    await fetch(`/api/agent/memory/${id}`, { method: "DELETE" });
  } else if (event.target.matches(".archive-memory")) {
    await fetch(`/api/agent/memory/${id}/archive`, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ archived: true }),
    });
  } else if (event.target.matches(".pin-memory")) {
    const pinned = !item.innerHTML.includes("fixada");
    await fetch(`/api/agent/memory/${id}/pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json; charset=utf-8" },
      body: JSON.stringify({ pinned }),
    });
  } else if (event.target.matches(".edit-memory")) {
    const value = window.prompt("Editar memoria:", item.querySelector("p")?.textContent || "");
    if (value) {
      await fetch(`/api/agent/memory/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({ value }),
      });
    }
  }
  await loadMemories(ui.memorySearch.value.trim());
}

async function loadPersonality() {
  const response = await fetch("/api/agent/personality");
  const data = await response.json();
  ui.personalityTone.value = data.tone || "parceiro fiel";
  ui.personalityDetail.value = data.detail_level || "equilibrado";
  ui.personalityEmoji.value = data.emoji_usage || "pouco";
  ui.personalityStyle.value = data.style || "";
  ui.personalityPosture.value = data.posture || "";
  ui.personalityTechnical.value = data.technical_default || "auto";
  ui.personalityAutoWeb.checked = Boolean(data.auto_web);
  ui.personalityAutoMemory.checked = Boolean(data.auto_memory);
}

async function savePersonality(event) {
  event.preventDefault();
  const payload = {
    tone: ui.personalityTone.value,
    detail_level: ui.personalityDetail.value,
    emoji_usage: ui.personalityEmoji.value,
    style: ui.personalityStyle.value,
    posture: ui.personalityPosture.value,
    technical_default: ui.personalityTechnical.value,
    auto_web: ui.personalityAutoWeb.checked,
    auto_memory: ui.personalityAutoMemory.checked,
  };
  await fetch("/api/agent/personality", {
    method: "PATCH",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });
  addMessage("agent", "Personalidade salva. Vou usar esse tom nas proximas respostas.");
}

async function resetPersonality() {
  await fetch("/api/agent/personality/reset", { method: "POST" });
  await loadPersonality();
}

on(ui.messageInput, "keydown", (event) => {
  if ((event.key === "Enter" && !event.shiftKey) || (event.key === "Enter" && event.ctrlKey)) {
    event.preventDefault();
    sendMessage();
  }
});

on(ui.messageInput, "input", autoResizeTextarea);
on(ui.chatForm, "submit", (event) => {
  event.preventDefault();
  sendMessage();
});
on(ui.analyzePcBtn, "click", () => analyzePc());
on(ui.deepResearchBtn, "click", () => deepResearch().catch((error) => addMessage("agent", error.message)));
on(ui.darkforestBtn, "click", () => {
  window.location.href = "/security";
});
on(ui.securityShortcutBtn, "click", () => {
  window.location.href = "/security";
});
on(ui.mcpBrasilBtn, "click", () => {
  window.location.href = "/mcp-brasil";
});
on(ui.retestGeminiBtn, "click", () => retestGemini().catch((error) => addMessage("agent", error.message)));
on(ui.detailsBtn, "click", openDetailsDrawer);
on(ui.activityDetailsBtn, "click", openDetailsDrawer);
on(ui.logoutBtn, "click", logout);
on(ui.closeDetailsBtn, "click", closeDetailsDrawer);
on(ui.memoryBtn, "click", () => {
  openModal(ui.memoryModal);
  loadMemories().catch(() => {});
});
on(ui.personalityBtn, "click", () => {
  openModal(ui.personalityModal);
  loadPersonality().catch(() => {});
});
on(ui.logsBtn, "click", () => {
  if (conversationId) openConversation(conversationId);
});
on(ui.matrixBtn, "click", () => loadCatalog().catch(() => {}));
on(ui.newConversationBtn, "click", () => createConversation());
on(ui.conversationSearch, "input", () => loadConversations(ui.conversationSearch.value.trim()).catch(() => {}));
on(ui.conversationList, "click", (event) => {
  const item = event.target.closest("[data-conversation-id]");
  if (!item) return;
  const id = item.dataset.conversationId;
  if (event.target.matches(".delete-conversation")) {
    deleteConversation(id).catch((error) => addMessage("agent", error.message));
  } else if (event.target.matches(".rename-conversation")) {
    renameConversation(id).catch((error) => addMessage("agent", error.message));
  } else {
    openConversation(id).catch((error) => addMessage("agent", error.message));
  }
});
on(ui.actionsBox, "click", (event) => {
  if (event.target.matches(".confirm-action")) {
    confirmAction(event.target.dataset.actionId).catch((error) => addMessage("agent", error.message));
  }
});
on(ui.memoryForm, "submit", saveMemory);
on(ui.memorySearch, "input", () => loadMemories(ui.memorySearch.value.trim()).catch(() => {}));
on(ui.memoryList, "click", (event) => handleMemoryAction(event).catch((error) => addMessage("agent", error.message)));
on(ui.personalityForm, "submit", savePersonality);
on(ui.resetPersonalityBtn, "click", () => resetPersonality().catch((error) => addMessage("agent", error.message)));

document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", () => closeModal(button.dataset.closeModal));
});
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    ui.messageInput.value = button.dataset.prompt || "";
    autoResizeTextarea();
    ui.messageInput.focus();
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeToolsMenu();
    closeDetailsDrawer();
  }
});
window.addEventListener("resize", updateComposerHeight);

requireLocalAuth();
setHasMessages(false);
updateComposerHeight();
loadConversations().catch(() => {});
ui.messageInput?.focus();
