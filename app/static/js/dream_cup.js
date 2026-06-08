(() => {
  "use strict";

  const formations = {
    "4-3-3": [["LW", "ST", "RW"], ["CM", "AM", "CM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-4-2": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-2-3-1": [["ST"], ["LW", "AM", "RW"], ["DM", "DM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "3-5-2": [["ST", "ST"], ["LM", "CM", "AM", "CM", "RM"], ["CB", "CB", "CB"], ["GK"]],
  };

  const roleBySlot = (slot) => {
    if (slot === "GK") return "GK";
    if (["CB", "LB", "RB"].includes(slot)) return "DF";
    if (["CM", "DM", "AM", "LM", "RM"].includes(slot)) return "MF";
    return "FW";
  };

  const roleLabel = (role) => ({
    GK: "Goleiro",
    DF: "Defesa",
    MF: "Meio",
    FW: "Ataque",
  }[role] || "Jogador");

  const state = {
    database: null,
    squads: [],
    formation: "4-3-3",
    mode: "classic",
    tactic: "balanced",
    lineup: [],
    currentSquad: null,
    usedSquads: new Set(),
    skips: 3,
    finished: false,
    filter: "",
  };

  const el = (id) => document.getElementById(id);
  const lineupEl = el("lineup");
  const rollBtn = el("rollBtn");
  const skipBtn = el("skipBtn");
  const playerList = el("playerList");
  const drawCard = el("drawCard");
  const rollTitle = el("rollTitle");
  const overallStat = el("overallStat");
  const chemStat = el("chemStat");
  const skipCount = el("skipCount");
  const simulateBtn = el("simulateBtn");
  const resetBtn = el("resetBtn");
  const simulationPanel = el("simulationPanel");
  const matchTimeline = el("matchTimeline");
  const resultCard = el("resultCard");
  const quickSimBtn = el("quickSimBtn");
  const playerSearch = el("playerSearch");
  const dbTeams = el("dbTeams");
  const dbSquads = el("dbSquads");
  const dbPlayers = el("dbPlayers");
  const dbSource = el("dbSource");

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("pt-BR");
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status} em ${url}`);
    return response.json();
  }

  async function loadDatabase() {
    try {
      state.database = await fetchJson("/static/data/dream_cup_database.json");
    } catch (_err) {
      state.database = await fetchJson("/static/data/dream_cup_seed.json");
    }
    state.squads = Array.isArray(state.database.squads) ? state.database.squads.filter(s => Array.isArray(s.players) && s.players.length) : [];
    if (!state.squads.length) throw new Error("Banco da Copa dos Sonhos vazio.");
    renderDatabaseStats();
  }

  function renderDatabaseStats() {
    const stats = state.database.stats || {};
    dbTeams.textContent = formatNumber(stats.teams || new Set(state.squads.map(s => s.nation)).size);
    dbSquads.textContent = formatNumber(stats.squads || state.squads.length);
    dbPlayers.textContent = formatNumber(stats.unique_players || new Set(state.squads.flatMap(s => s.players.map(p => p.id || p.name))).size);
    dbSource.textContent = state.database.source || "Banco local da Copa dos Sonhos";
  }

  function flattenFormation() {
    return formations[state.formation]
      .map((row, rowIndex) => row.map((pos, slotIndex) => ({ pos, row: rowIndex, slotIndex, player: null })))
      .flat();
  }

  function groupedLineup() {
    const rows = formations[state.formation].length;
    return Array.from({ length: rows }, (_, i) => state.lineup.filter(slot => slot.row === i));
  }

  function playerKey(player) {
    return `${player.id || player.name}-${player.nation}-${player.year}`;
  }

  function availableSlotsFor(player) {
    return state.lineup.filter(slot => !slot.player && roleBySlot(slot.pos) === player.role);
  }

  function chosenPlayerKeys() {
    return new Set(state.lineup.filter(s => s.player).map(s => playerKey(s.player)));
  }

  function renderLineup() {
    lineupEl.innerHTML = "";
    groupedLineup().forEach(row => {
      const rowNode = document.createElement("div");
      rowNode.className = "pitch-row";
      row.forEach(slot => {
        const node = document.createElement("div");
        node.className = `slot ${slot.player ? "filled" : ""}`;
        const pos = document.createElement("div");
        pos.className = "slot-pos";
        pos.textContent = slot.pos;
        const name = document.createElement("div");
        name.className = "slot-name";
        name.textContent = slot.player ? displayName(slot.player) : "Vaga aberta";
        const meta = document.createElement("div");
        meta.className = "slot-meta";
        meta.textContent = slot.player ? playerMeta(slot.player) : roleLabel(roleBySlot(slot.pos));
        node.append(pos, name, meta);
        if (slot.player) {
          const rating = document.createElement("span");
          rating.className = "rating-badge";
          rating.textContent = state.mode === "memory" ? "?" : slot.player.rating;
          node.appendChild(rating);
        }
        rowNode.appendChild(node);
      });
      lineupEl.appendChild(rowNode);
    });
    updateStats();
  }

  function displayName(player) {
    if (state.mode !== "memory") return player.name;
    return `${player.role} ${player.shirt_number ? "#" + player.shirt_number : "?"}`;
  }

  function playerMeta(player) {
    const shirt = player.shirt_number ? `#${player.shirt_number} · ` : "";
    return `${shirt}${player.nation} ${player.year} · ${player.trait || roleLabel(player.role)}`;
  }

  function calculateChemistry() {
    const picked = state.lineup.filter(slot => slot.player).map(slot => slot.player);
    if (!picked.length) return 0;
    const nations = new Map();
    const decades = new Map();
    let roleFit = 0;
    picked.forEach(p => {
      nations.set(p.nation, (nations.get(p.nation) || 0) + 1);
      const decade = Math.floor(Number(p.year || 0) / 10) * 10;
      decades.set(decade, (decades.get(decade) || 0) + 1);
      roleFit += 1;
    });
    const sameNation = Math.max(...nations.values());
    const sameDecade = Math.max(...decades.values());
    const mixPenalty = Math.max(0, nations.size - 4) * 3;
    return Math.max(20, Math.min(100, Math.round(35 + sameNation * 5 + sameDecade * 3 + roleFit * 2 - mixPenalty)));
  }

  function calculateOverall() {
    const picked = state.lineup.filter(slot => slot.player).map(slot => slot.player);
    if (!picked.length) return 0;
    const avg = picked.reduce((sum, p) => sum + Number(p.rating || 70), 0) / picked.length;
    return Math.round(avg);
  }

  function updateStats() {
    const overall = calculateOverall();
    const chem = calculateChemistry();
    overallStat.textContent = `OVR ${overall || "--"}`;
    chemStat.textContent = `QUI ${chem || "--"}`;
    simulateBtn.disabled = state.lineup.some(slot => !slot.player);
  }

  function drawSquad() {
    if (!state.squads.length) return null;
    const compatible = state.squads.filter(squad => {
      if (state.usedSquads.has(squad.id)) return false;
      return squad.players.some(player => availableSlotsFor(player).length > 0 && !chosenPlayerKeys().has(playerKey(player)));
    });
    const pool = compatible.length ? compatible : state.squads;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  function renderDrawCard() {
    if (!state.currentSquad) {
      drawCard.className = "draw-card empty";
      drawCard.innerHTML = "<p>Uma seleção histórica vai aparecer aqui. Escolha um jogador compatível com as vagas abertas.</p>";
      return;
    }
    const squad = state.currentSquad;
    drawCard.className = "draw-card";
    drawCard.innerHTML = `
      <p class="eyebrow">${squad.tournament || "Copa do Mundo"}</p>
      <h3>${escapeHtml(squad.nation)} ${squad.year}</h3>
      <p>${escapeHtml(squad.aura || "elenco real")} · força ${squad.strength || "--"} · ${squad.players.length} jogadores no elenco</p>
    `;
  }

  function renderPlayers() {
    playerList.innerHTML = "";
    if (!state.currentSquad) {
      playerList.innerHTML = `<div class="draw-card empty"><p>Role uma seleção para liberar o elenco.</p></div>`;
      return;
    }

    const picked = chosenPlayerKeys();
    const term = state.filter.trim().toLowerCase();
    const players = state.currentSquad.players
      .filter(player => {
        if (!term) return true;
        const text = `${player.name} ${player.role} ${player.position_name || ""} ${player.shirt_number || ""}`.toLowerCase();
        return text.includes(term);
      })
      .slice()
      .sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0));

    if (!players.length) {
      playerList.innerHTML = `<div class="draw-card empty"><p>Nenhum jogador encontrado nesse filtro.</p></div>`;
      return;
    }

    players.forEach(player => {
      const slots = availableSlotsFor(player);
      const already = picked.has(playerKey(player));
      const disabled = slots.length === 0 || already;
      const button = document.createElement("button");
      button.className = "player-card";
      button.type = "button";
      button.disabled = disabled;
      button.innerHTML = `
        <span class="shirt">${player.shirt_number || player.role}</span>
        <span>
          <span class="player-name">${escapeHtml(displayName(player))}</span>
          <span class="player-meta">${escapeHtml(playerMeta(player))}</span>
        </span>
        <span class="player-role">${state.mode === "memory" ? "?" : (player.rating || "--")} · ${player.role}</span>
      `;
      button.addEventListener("click", () => selectPlayer(player));
      playerList.appendChild(button);
    });
  }

  function selectPlayer(player) {
    const slots = availableSlotsFor(player);
    if (!slots.length) return;
    slots[0].player = {
      ...player,
      nation: state.currentSquad.nation,
      year: state.currentSquad.year,
      tournament: state.currentSquad.tournament,
    };
    state.usedSquads.add(state.currentSquad.id);
    state.currentSquad = null;
    state.filter = "";
    playerSearch.value = "";
    renderAll();
  }

  function roll() {
    if (state.finished) return;
    state.currentSquad = drawSquad();
    if (state.currentSquad) state.usedSquads.add(state.currentSquad.id);
    rollTitle.textContent = state.currentSquad ? `${state.currentSquad.nation} ${state.currentSquad.year}` : "Sem elenco compatível";
    renderAll();
  }

  function skip() {
    if (!state.currentSquad || state.skips <= 0) return;
    state.skips -= 1;
    state.currentSquad = null;
    renderAll();
  }

  function resetGame() {
    state.lineup = flattenFormation();
    state.currentSquad = null;
    state.usedSquads = new Set();
    state.skips = 3;
    state.finished = false;
    state.filter = "";
    playerSearch.value = "";
    simulationPanel.classList.add("hidden");
    resultCard.classList.add("hidden");
    resultCard.innerHTML = "";
    matchTimeline.innerHTML = "";
    renderAll();
  }

  function renderAll() {
    skipCount.textContent = state.skips;
    skipBtn.disabled = !state.currentSquad || state.skips <= 0;
    renderLineup();
    renderDrawCard();
    renderPlayers();
  }

  function tacticalBonus() {
    const overall = calculateOverall();
    const chem = calculateChemistry();
    if (state.tactic === "attack") return overall > 86 ? 5 : -2;
    if (state.tactic === "control") return chem > 70 ? 4 : -1;
    return 2;
  }

  function pickOpponent(roundIndex) {
    const candidates = state.squads.filter(s => s.players.length >= 15);
    const squad = candidates[Math.floor(Math.random() * candidates.length)];
    const base = Number(squad?.strength || 76);
    return {
      name: squad ? `${squad.nation} ${squad.year}` : "Adversário histórico",
      power: Math.round(base + roundIndex * 1.6 + Math.random() * 7),
    };
  }

  function simulateScore(opponent, roundIndex) {
    const overall = calculateOverall();
    const chem = calculateChemistry();
    const teamPower = overall + chem * 0.22 + tacticalBonus() + Math.random() * 11;
    const oppPower = opponent.power + Math.random() * 10;
    let goalsFor = Math.max(0, Math.round((teamPower - oppPower + 16) / 8 + Math.random() * 2));
    let goalsAgainst = Math.max(0, Math.round((oppPower - teamPower + 10) / 9 + Math.random() * 1.5));

    if (roundIndex >= 3 && teamPower < oppPower - 5) {
      goalsFor = Math.min(goalsFor, Math.floor(Math.random() * 2));
      goalsAgainst = Math.max(goalsAgainst, goalsFor + 1);
    }

    const sevenChance = Math.max(0, (overall - 88) * 0.025 + (chem - 75) * 0.01 + (state.tactic === "attack" ? 0.05 : 0));
    if (Math.random() < sevenChance) {
      goalsFor = 7;
      goalsAgainst = 0;
    }

    if (goalsFor === goalsAgainst && roundIndex >= 3) {
      if (teamPower >= oppPower) goalsFor += 1;
      else goalsAgainst += 1;
    }

    return [Math.min(9, goalsFor), Math.min(7, goalsAgainst), teamPower];
  }

  function simulateCup(auto = false) {
    if (state.lineup.some(slot => !slot.player)) return;
    state.finished = true;
    simulationPanel.classList.remove("hidden");
    matchTimeline.innerHTML = "";
    resultCard.classList.add("hidden");
    resultCard.innerHTML = "";

    const stages = ["Grupo 1", "Grupo 2", "Grupo 3", "Oitavas", "Quartas", "Semifinal", "Final"];
    let wonCup = true;
    let sevenZero = false;
    const rows = [];

    stages.forEach((stage, index) => {
      const opponent = pickOpponent(index);
      const [gf, ga] = simulateScore(opponent, index);
      if (gf === 7 && ga === 0) sevenZero = true;
      if (index >= 3 && gf < ga) wonCup = false;
      rows.push({ stage, opponent, gf, ga });
      if (!wonCup) return;
    });

    const effectiveRows = [];
    for (const row of rows) {
      effectiveRows.push(row);
      if (["Oitavas", "Quartas", "Semifinal", "Final"].includes(row.stage) && row.gf < row.ga) break;
    }

    const renderRow = (row, idx) => {
      const node = document.createElement("div");
      node.className = "match-row";
      node.innerHTML = `
        <span class="match-stage">${row.stage}</span>
        <strong>Seu time x ${escapeHtml(row.opponent.name)}</strong>
        <span class="match-score">${row.gf} x ${row.ga}</span>
      `;
      matchTimeline.appendChild(node);
    };

    if (auto) {
      effectiveRows.forEach(renderRow);
      renderResult(effectiveRows, wonCup, sevenZero);
      return;
    }

    effectiveRows.forEach((row, idx) => {
      setTimeout(() => {
        renderRow(row, idx);
        if (idx === effectiveRows.length - 1) renderResult(effectiveRows, wonCup, sevenZero);
      }, idx * 520);
    });
  }

  function renderResult(rows, wonCup, sevenZero) {
    const last = rows[rows.length - 1];
    const title = sevenZero
      ? "Você achou o 7 a 0."
      : wonCup
        ? "Campeão, mas sem massacre."
        : `Caiu em ${last.stage}.`;
    const text = sevenZero
      ? "Seu elenco virou lenda. Time forte, química no ponto e noite perfeita."
      : wonCup
        ? "Levantou a taça, mas o 7 a 0 não veio. O jogo ainda pode te cobrar mais precisão."
        : "Nome pesado não ganha sozinho. A Copa pune química baixa, buracos de posição e azar.";
    resultCard.classList.remove("hidden");
    resultCard.innerHTML = `
      <h3>${title}</h3>
      <p>${text}</p>
      <p><strong>OVR:</strong> ${calculateOverall()} · <strong>Química:</strong> ${calculateChemistry()} · <strong>Tática:</strong> ${labelTactic(state.tactic)}</p>
    `;
  }

  function labelTactic(tactic) {
    return { balanced: "Equilibrado", attack: "Ataque total", control: "Controle" }[tactic] || tactic;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    }[ch]));
  }

  function bindControls() {
    document.querySelectorAll("[data-formation]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-formation]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.formation = btn.dataset.formation;
        resetGame();
      });
    });

    document.querySelectorAll("[data-mode]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-mode]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.mode = btn.dataset.mode;
        renderAll();
      });
    });

    document.querySelectorAll("[data-tactic]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-tactic]").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.tactic = btn.dataset.tactic;
        updateStats();
      });
    });

    rollBtn.addEventListener("click", roll);
    skipBtn.addEventListener("click", skip);
    resetBtn.addEventListener("click", resetGame);
    simulateBtn.addEventListener("click", () => simulateCup(false));
    quickSimBtn.addEventListener("click", () => simulateCup(true));
    playerSearch.addEventListener("input", () => {
      state.filter = playerSearch.value || "";
      renderPlayers();
    });
  }

  async function init() {
    bindControls();
    state.lineup = flattenFormation();
    try {
      await loadDatabase();
    } catch (err) {
      drawCard.className = "draw-card empty";
      drawCard.innerHTML = `<p>Não consegui carregar o banco do jogo: ${escapeHtml(err.message)}</p>`;
    }
    renderAll();
  }

  init();
})();
