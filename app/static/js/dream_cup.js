(() => {
  "use strict";

  const formations = {
    "4-3-3": [["LW", "ST", "RW"], ["CM", "AM", "CM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-4-2": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-2-3-1": [["ST"], ["LW", "AM", "RW"], ["DM", "DM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "3-5-2": [["ST", "ST"], ["LM", "CM", "AM", "CM", "RM"], ["CB", "CB", "CB"], ["GK"]],
  };
  const ROLE_SLOTS = {
    GK: ["GK"],
    DF: ["CB", "LB", "RB"],
    MF: ["CM", "DM", "AM", "LM", "RM"],
    FW: ["ST", "LW", "RW"],
  };
  const OPPONENT_RANGES = [[76, 85], [78, 86], [80, 87], [82, 88], [85, 91], [88, 94], [90, 97]];

  const roleBySlot = (slot) => {
    if (slot === "GK") return "GK";
    if (["CB", "LB", "RB"].includes(slot)) return "DF";
    if (["CM", "DM", "AM", "LM", "RM"].includes(slot)) return "MF";
    return "FW";
  };
  const roleLabel = (role) => ({ GK: "Goleiro", DF: "Defensor", MF: "Meio-campista", FW: "Atacante" }[role] || "Jogador");
  const normalizeText = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  function compatibleSlotsForPlayer(player) {
    const name = normalizeText(player.name);
    const position = normalizeText(`${player.position_code || ""} ${player.position_name || ""}`);
    const trait = normalizeText(`${player.trait || ""} ${player.trait_label || ""}`);
    if (player.role === "GK") return ["GK"];
    if (name.includes("roberto carlos")) return ["LB", "LM"];
    if (name === "cafu" || name.includes("cafu")) return ["RB", "RM"];
    if (name === "ronaldo") return ["ST"];
    if (name.includes("rivaldo")) return ["AM", "LW", "ST"];
    if (name.includes("ze roberto")) return ["CM", "LM", "LB"];
    if (player.role === "DF") {
      if (position.includes("left") || position.includes("esquerd")) return ["LB", "CB"];
      if (position.includes("right") || position.includes("direit")) return ["RB", "CB"];
      return ["CB", "LB", "RB"];
    }
    if (player.role === "MF") {
      if (position.includes("defensive") || trait.includes("defens")) return ["DM", "CM"];
      if (position.includes("attacking") || trait.includes("maestro") || trait.includes("playmaker")) return ["AM", "CM"];
      if (position.includes("left")) return ["LM", "CM"];
      if (position.includes("right")) return ["RM", "CM"];
      return ["CM", "DM", "AM", "LM", "RM"];
    }
    if (position.includes("wing") || trait.includes("velocidade")) return ["LW", "RW", "ST"];
    return ["ST", "LW", "RW"];
  }

  function preferredSlotsForPlayer(player) {
    const slots = compatibleSlotsForPlayer(player);
    if (player.role === "DF" && slots.length === 3) return ["CB"];
    if (player.role === "MF" && slots.length === 5) return ["CM"];
    if (player.role === "FW" && slots.length === 3) return ["ST"];
    return slots.slice(0, Math.min(2, slots.length));
  }

  function positionMetrics(lineup) {
    const filled = lineup.filter((slot) => slot.player);
    if (!filled.length) return { fit: 0, outOfPosition: 0 };
    const preferred = filled.filter((slot) => preferredSlotsForPlayer(slot.player).includes(slot.pos)).length;
    return { fit: preferred / filled.length, outOfPosition: filled.length - preferred };
  }

  function lineupOverall(lineup) {
    const players = lineup.filter((slot) => slot.player).map((slot) => slot.player);
    if (!players.length) return 0;
    return players.reduce((sum, player) => sum + Number(player.rating || 70), 0) / players.length;
  }

  function lineupChemistry(lineup) {
    const players = lineup.filter((slot) => slot.player).map((slot) => slot.player);
    if (!players.length) return 0;
    const nations = new Map();
    const decades = new Map();
    players.forEach((player) => {
      nations.set(player.nation, (nations.get(player.nation) || 0) + 1);
      const decade = Math.floor(Number(player.year || 0) / 10) * 10;
      decades.set(decade, (decades.get(decade) || 0) + 1);
    });
    const sameNation = Math.max(...nations.values());
    const sameDecade = Math.max(...decades.values());
    const mixPenalty = Math.max(0, nations.size - 4) * 4;
    return Math.max(15, Math.min(100, Math.round(31 + sameNation * 5 + sameDecade * 3 + players.length * 2 - mixPenalty)));
  }

  function tacticBonus(tactic, overall, chemistry) {
    if (tactic === "attack") return overall >= 88 && chemistry >= 65 ? 2.5 : -3;
    if (tactic === "control") return chemistry >= 72 ? 2.5 : -2;
    return 1;
  }

  function calculateTeamPower(lineup, tactic = "balanced", variance = 0) {
    const overall = lineupOverall(lineup);
    const chemistry = lineupChemistry(lineup);
    const metrics = positionMetrics(lineup);
    const lowChemPenalty = chemistry < 45 ? (45 - chemistry) * 0.24 : 0;
    const incompletePenalty = Math.max(0, 11 - lineup.filter((slot) => slot.player).length) * 3;
    return Number((
      overall * 0.65 +
      chemistry * 0.22 +
      metrics.fit * 10 +
      tacticBonus(tactic, overall, chemistry) -
      metrics.outOfPosition * 2.8 -
      lowChemPenalty -
      incompletePenalty +
      variance
    ).toFixed(2));
  }

  function calculateOpponentPower(stageIndex, randomValue = Math.random()) {
    const [min, max] = OPPONENT_RANGES[Math.min(stageIndex, OPPONENT_RANGES.length - 1)];
    return Number((min + (max - min) * randomValue).toFixed(2));
  }

  function simulateMatch(lineup, tactic, opponentPower, stageIndex, randomValue = Math.random()) {
    const overall = lineupOverall(lineup);
    const chemistry = lineupChemistry(lineup);
    const fit = positionMetrics(lineup).fit;
    const teamPower = calculateTeamPower(lineup, tactic, (randomValue - 0.5) * 7);
    const knockoutPressure = stageIndex >= 3 ? (stageIndex - 2) * 1.15 : 0;
    const difference = teamPower - opponentPower - knockoutPressure;
    let goalsFor = Math.max(0, Math.min(5, Math.floor(1.25 + difference / 9 + randomValue * 1.8)));
    let goalsAgainst = Math.max(0, Math.min(6, Math.floor(1.2 - difference / 10 + (1 - randomValue) * 1.8)));
    const canSeven = overall >= 88 && chemistry >= 70 && fit >= 0.8 && difference >= 12;
    if (canSeven && randomValue > 0.985) {
      goalsFor = 7;
      goalsAgainst = 0;
    }
    if (stageIndex >= 3 && goalsFor === goalsAgainst) {
      if (difference > 4 && randomValue > 0.38) goalsFor += 1;
      else goalsAgainst += 1;
    }
    return { goalsFor, goalsAgainst, teamPower, opponentPower, sevenZero: goalsFor === 7 && goalsAgainst === 0 };
  }

  const gameApi = { compatibleSlotsForPlayer, preferredSlotsForPlayer, positionMetrics, calculateTeamPower, calculateOpponentPower, simulateMatch };
  if (typeof module !== "undefined" && module.exports) module.exports = gameApi;
  if (typeof document === "undefined") return;
  if (typeof window !== "undefined") window.DreamCupGame = gameApi;

  const state = {
    database: null, squads: [], formation: "4-3-3", mode: "classic", tactic: "balanced",
    lineup: [], currentSquad: null, usedSquads: new Set(), skips: 3, finished: false,
    filter: "", selectedSlotIndex: null, draftMessage: "Role uma seleção para começar.",
  };
  const el = (id) => document.getElementById(id);
  const lineupEl = el("lineup"), rollBtn = el("rollBtn"), skipBtn = el("skipBtn"), playerList = el("playerList");
  const drawCard = el("drawCard"), rollTitle = el("rollTitle"), overallStat = el("overallStat"), chemStat = el("chemStat");
  const skipCount = el("skipCount"), simulateBtn = el("simulateBtn"), resetBtn = el("resetBtn"), simulationPanel = el("simulationPanel");
  const matchTimeline = el("matchTimeline"), resultCard = el("resultCard"), quickSimBtn = el("quickSimBtn"), playerSearch = el("playerSearch");
  const dbSource = el("dbSource"), optionsToggle = el("optionsToggle"), optionsPanel = el("optionsPanel"), pickedStat = el("pickedStat");
  const teamState = el("teamState"), simulateHint = el("simulateHint"), draftStatus = el("draftStatus"), lineupStatus = el("lineupStatus");

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status} em ${url}`);
    return response.json();
  }
  async function loadDatabase() {
    try { state.database = await fetchJson("/static/data/dream_cup_database.json"); }
    catch (_err) { state.database = await fetchJson("/static/data/dream_cup_seed.json"); }
    state.squads = Array.isArray(state.database.squads) ? state.database.squads.filter((squad) => Array.isArray(squad.players) && squad.players.length) : [];
    if (!state.squads.length) throw new Error("Banco da Copa dos Sonhos vazio.");
    if (dbSource) dbSource.textContent = state.database.source || "Banco local da Copa dos Sonhos";
  }
  const flattenFormation = () => formations[state.formation].flatMap((row, rowIndex) => row.map((pos, slotIndex) => ({ pos, row: rowIndex, slotIndex, player: null })));
  const groupedLineup = () => Array.from({ length: formations[state.formation].length }, (_, index) => state.lineup.filter((slot) => slot.row === index));
  const playerKey = (player) => `${player.id || player.name}-${player.nation}-${player.year}`;
  const chosenPlayerKeys = () => new Set(state.lineup.filter((slot) => slot.player).map((slot) => playerKey(slot.player)));
  const availableSlotsFor = (player) => state.lineup.filter((slot) => !slot.player && compatibleSlotsForPlayer(player).includes(slot.pos));
  const displayName = (player) => state.mode === "memory" ? `${player.role} ${player.shirt_number ? `#${player.shirt_number}` : "?"}` : String(player.name || "Jogador sem nome").trim();
  const playerMeta = (player) => `${player.shirt_number ? `#${player.shirt_number} · ` : ""}${player.nation || "Seleção"} ${player.year} · ${player.trait_label || player.trait || roleLabel(player.role)}`;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));

  function canMoveTo(sourceIndex, targetIndex) {
    const source = state.lineup[sourceIndex], target = state.lineup[targetIndex];
    if (!source?.player || sourceIndex === targetIndex) return false;
    if (!compatibleSlotsForPlayer(source.player).includes(target.pos)) return false;
    return !target.player || compatibleSlotsForPlayer(target.player).includes(source.pos);
  }
  function movePlayer(sourceIndex, targetIndex) {
    if (!canMoveTo(sourceIndex, targetIndex)) return false;
    const source = state.lineup[sourceIndex], target = state.lineup[targetIndex];
    [source.player, target.player] = [target.player, source.player];
    state.selectedSlotIndex = null;
    renderAll();
    return true;
  }
  function handleSlotAction(index) {
    const slot = state.lineup[index];
    if (state.selectedSlotIndex !== null) {
      if (state.selectedSlotIndex === index) state.selectedSlotIndex = null;
      else if (!movePlayer(state.selectedSlotIndex, index)) state.selectedSlotIndex = slot.player ? index : null;
    } else if (slot.player) state.selectedSlotIndex = index;
    renderLineup();
  }
  function renderLineup() {
    lineupEl.innerHTML = "";
    groupedLineup().forEach((row) => {
      const rowNode = document.createElement("div");
      rowNode.className = "pitch-row";
      row.forEach((slot) => {
        const index = state.lineup.indexOf(slot);
        const node = document.createElement("button");
        const isSelected = state.selectedSlotIndex === index;
        const isTarget = state.selectedSlotIndex !== null && canMoveTo(state.selectedSlotIndex, index);
        node.type = "button";
        node.className = `slot ${slot.player ? "filled" : ""} ${isSelected ? "selected" : ""} ${isTarget ? "move-target" : ""}`;
        node.setAttribute("aria-label", slot.player ? `${displayName(slot.player)} em ${slot.pos}` : `Vaga ${slot.pos}`);
        node.innerHTML = `<span class="slot-pos">${slot.pos}</span><span class="slot-name">${escapeHtml(slot.player ? displayName(slot.player) : roleLabel(roleBySlot(slot.pos)))}</span><span class="slot-meta">${slot.player ? escapeHtml(playerMeta(slot.player)) : ""}</span>${slot.player ? `<span class="rating-badge">${state.mode === "memory" ? "?" : slot.player.rating}</span>` : ""}`;
        node.addEventListener("click", () => handleSlotAction(index));
        rowNode.appendChild(node);
      });
      lineupEl.appendChild(rowNode);
    });
    lineupStatus.textContent = state.selectedSlotIndex === null ? "Clique em um jogador no campo para reorganizar." : "Agora escolha uma vaga destacada para mover ou trocar.";
    updateStats();
  }
  function updateStats() {
    const overall = Math.round(lineupOverall(state.lineup));
    const chemistry = lineupChemistry(state.lineup);
    const pickedCount = state.lineup.filter((slot) => slot.player).length;
    const missing = Math.max(0, state.lineup.length - pickedCount);
    const complete = missing === 0;
    overallStat.textContent = `OVR ${overall || "--"}`;
    chemStat.textContent = `QUI ${chemistry || "--"}`;
    pickedStat.textContent = `${pickedCount}/${state.lineup.length}`;
    teamState.textContent = complete ? "Time pronto" : `Faltam ${missing} vaga${missing === 1 ? "" : "s"}`;
    simulateHint.textContent = complete ? "Onze fechado. A campanha pune química baixa e posições improvisadas." : "Complete os 11 para liberar a simulação.";
    simulateBtn.disabled = !complete;
    simulateBtn.textContent = complete ? "Simular Copa" : `Faltam ${missing}`;
  }
  function drawSquad() {
    const picked = chosenPlayerKeys();
    const compatible = state.squads.filter((squad) => !state.usedSquads.has(squad.id) && squad.players.some((player) => availableSlotsFor(player).length && !picked.has(playerKey(player))));
    return compatible.length ? compatible[Math.floor(Math.random() * compatible.length)] : null;
  }
  function renderDrawCard() {
    draftStatus.textContent = state.draftMessage;
    if (!state.currentSquad) {
      drawCard.className = "draw-card empty";
      drawCard.innerHTML = "<p>O próximo elenco só aparece quando você rolar.</p>";
      return;
    }
    drawCard.className = "draw-card dealt";
    drawCard.innerHTML = `<p class="eyebrow">${escapeHtml(state.currentSquad.tournament || "Copa do Mundo")}</p><h3>${escapeHtml(state.currentSquad.nation)} ${state.currentSquad.year}</h3><p>${escapeHtml(state.currentSquad.aura || "elenco real")} · força ${state.currentSquad.strength || "--"}</p>`;
  }
  function renderPlayers() {
    playerList.innerHTML = "";
    if (!state.currentSquad) {
      playerList.innerHTML = '<div class="draw-card empty"><p>O deck será liberado depois do sorteio.</p></div>';
      return;
    }
    const picked = chosenPlayerKeys();
    const term = state.filter.trim().toLowerCase();
    const players = state.currentSquad.players.filter((player) => !term || `${player.name} ${player.role} ${player.position_name || ""} ${player.shirt_number || ""}`.toLowerCase().includes(term)).slice().sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0));
    players.forEach((player) => {
      const disabled = !availableSlotsFor(player).length || picked.has(playerKey(player));
      const button = document.createElement("button");
      button.className = `player-card ${disabled ? "incompatible" : ""}`;
      button.type = "button";
      button.disabled = disabled;
      button.innerHTML = `<span class="shirt">#${player.shirt_number || "—"}</span><span class="player-copy"><span class="player-name">${escapeHtml(displayName(player))}</span><span class="player-meta">${escapeHtml(playerMeta(player))}</span><span class="player-trait">${escapeHtml(player.trait_label || player.trait || roleLabel(player.role))}</span></span><span class="overall-badge"><strong>${state.mode === "memory" ? "?" : player.rating || "--"}</strong><small>${escapeHtml(player.role_label || roleLabel(player.role))}</small></span>`;
      button.addEventListener("click", () => selectPlayer(player));
      playerList.appendChild(button);
    });
  }
  function selectPlayer(player) {
    const slots = availableSlotsFor(player);
    if (!slots.length || !state.currentSquad) return;
    const preferred = preferredSlotsForPlayer(player);
    const target = slots.find((slot) => preferred.includes(slot.pos)) || slots[0];
    target.player = { ...player, nation: state.currentSquad.nation, year: state.currentSquad.year, tournament: state.currentSquad.tournament };
    state.usedSquads.add(state.currentSquad.id);
    state.currentSquad = null;
    state.filter = "";
    state.draftMessage = "Jogador escalado. Role o próximo elenco.";
    playerSearch.value = "";
    renderAll();
  }
  function roll() {
    if (state.finished || state.currentSquad) return;
    state.currentSquad = drawSquad();
    if (!state.currentSquad) {
      state.draftMessage = "Sem opção compatível. O draft foi encerrado.";
      renderAll();
      return;
    }
    state.usedSquads.add(state.currentSquad.id);
    state.draftMessage = state.skips > 0 ? "Escolha um jogador deste elenco ou use um coringa." : "Sem coringas: escolha alguém deste elenco.";
    rollTitle.textContent = `${state.currentSquad.nation} ${state.currentSquad.year}`;
    renderAll();
  }
  function skip() {
    if (!state.currentSquad || state.skips <= 0) return;
    state.skips -= 1;
    state.currentSquad = null;
    state.draftMessage = `Coringa usado. Restam ${state.skips}.`;
    rollTitle.textContent = "Role o dado";
    renderAll();
  }
  function resetGame() {
    state.lineup = flattenFormation();
    state.currentSquad = null;
    state.usedSquads = new Set();
    state.skips = 3;
    state.finished = false;
    state.filter = "";
    state.selectedSlotIndex = null;
    state.draftMessage = "Role uma seleção para começar.";
    playerSearch.value = "";
    rollTitle.textContent = "Role o dado";
    simulationPanel.classList.add("hidden");
    resultCard.classList.add("hidden");
    resultCard.innerHTML = "";
    matchTimeline.innerHTML = "";
    renderAll();
  }
  function renderAll() {
    skipCount.textContent = state.skips;
    rollBtn.disabled = Boolean(state.currentSquad) || state.finished;
    skipBtn.disabled = !state.currentSquad || state.skips <= 0;
    renderLineup();
    renderDrawCard();
    renderPlayers();
  }
  function pickOpponent(stageIndex) {
    const candidates = state.squads.filter((squad) => squad.players.length >= 15);
    const squad = candidates[Math.floor(Math.random() * candidates.length)];
    return { name: squad ? `${squad.nation} ${squad.year}` : "Adversário histórico", power: calculateOpponentPower(stageIndex) };
  }
  function simulateCup(auto = false) {
    if (state.lineup.some((slot) => !slot.player)) return;
    state.finished = true;
    simulationPanel.classList.remove("hidden");
    matchTimeline.innerHTML = "";
    resultCard.classList.add("hidden");
    const stages = ["Grupo 1", "Grupo 2", "Grupo 3", "Oitavas", "Quartas", "Semifinal", "Final"];
    const rows = [];
    let sevenZero = false;
    for (let index = 0; index < stages.length; index += 1) {
      const opponent = pickOpponent(index);
      const result = simulateMatch(state.lineup, state.tactic, opponent.power, index);
      sevenZero ||= result.sevenZero;
      rows.push({ stage: stages[index], opponent, gf: result.goalsFor, ga: result.goalsAgainst });
      if (index >= 3 && result.goalsFor < result.goalsAgainst) break;
    }
    const wonCup = rows.length === stages.length && rows[rows.length - 1].gf > rows[rows.length - 1].ga;
    const renderRow = (row) => {
      const node = document.createElement("div");
      node.className = "match-row";
      node.innerHTML = `<span class="match-stage">${row.stage}</span><strong>Seu time × ${escapeHtml(row.opponent.name)}</strong><span class="match-score">${row.gf} × ${row.ga}</span>`;
      matchTimeline.appendChild(node);
    };
    if (auto) {
      rows.forEach(renderRow);
      renderResult(rows, wonCup, sevenZero);
      return;
    }
    rows.forEach((row, index) => setTimeout(() => {
      renderRow(row);
      if (index === rows.length - 1) renderResult(rows, wonCup, sevenZero);
    }, index * 520));
  }
  function renderResult(rows, wonCup, sevenZero) {
    const last = rows[rows.length - 1];
    const metrics = positionMetrics(state.lineup);
    const title = sevenZero ? "Você achou o raríssimo 7 a 0." : wonCup ? "Campeão dos sonhos." : `Caiu em ${last.stage}.`;
    resultCard.classList.remove("hidden");
    resultCard.innerHTML = `<h3>${title}</h3><p>${wonCup ? "O time sobreviveu à campanha." : "A Copa cobrou força, química e encaixe tático."}</p><p><strong>OVR:</strong> ${Math.round(lineupOverall(state.lineup))} · <strong>Química:</strong> ${lineupChemistry(state.lineup)} · <strong>Encaixe:</strong> ${Math.round(metrics.fit * 100)}%</p>`;
  }
  function bindControls() {
    optionsToggle?.addEventListener("click", () => {
      const open = optionsPanel.classList.contains("hidden");
      optionsPanel.classList.toggle("hidden", !open);
      optionsToggle.setAttribute("aria-expanded", String(open));
    });
    document.querySelectorAll("[data-formation]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-formation]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.formation = button.dataset.formation;
      resetGame();
    }));
    document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.mode = button.dataset.mode;
      renderAll();
    }));
    document.querySelectorAll("[data-tactic]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-tactic]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.tactic = button.dataset.tactic;
      updateStats();
    }));
    rollBtn.addEventListener("click", roll);
    skipBtn.addEventListener("click", skip);
    resetBtn.addEventListener("click", resetGame);
    simulateBtn.addEventListener("click", () => simulateCup(false));
    quickSimBtn.addEventListener("click", () => simulateCup(true));
    playerSearch.addEventListener("input", () => { state.filter = playerSearch.value || ""; renderPlayers(); });
  }
  async function init() {
    bindControls();
    state.lineup = flattenFormation();
    try { await loadDatabase(); }
    catch (error) { drawCard.innerHTML = `<p>Não consegui carregar o banco do jogo: ${escapeHtml(error.message)}</p>`; }
    renderAll();
  }
  init();
})();
