(() => {
  "use strict";

  const formations = {
    "4-3-3": [["LW", "ST", "RW"], ["CM", "AM", "CM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-4-2": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-2-3-1": [["ST"], ["LW", "AM", "RW"], ["DM", "DM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "3-5-2": [["ST", "ST"], ["LM", "CM", "AM", "CM", "RM"], ["CB", "CB", "CB"], ["GK"]],
  };

  const squads = [
    { nation: "Brasil", flag: "🇧🇷", year: 1970, aura: "arte e domínio", players: [
      p("Pelé", "FW", 99, "Finalizador genial"), p("Jairzinho", "FW", 95, "Ponta imparável"), p("Tostão", "FW", 93, "Falso 9 cerebral"), p("Rivelino", "MF", 94, "Canhota de elite"), p("Gérson", "MF", 93, "Maestro"), p("Carlos Alberto", "DF", 94, "Lateral capitão"), p("Clodoaldo", "MF", 90, "Equilíbrio"), p("Britto", "DF", 88, "Zagueiro forte"), p("Piazza", "DF", 89, "Saída limpa"), p("Félix", "GK", 86, "Goleiro seguro") ]},
    { nation: "Brasil", flag: "🇧🇷", year: 2002, aura: "tridente pesado", players: [
      p("Ronaldo", "FW", 97, "Fenômeno"), p("Ronaldinho", "FW", 95, "Magia"), p("Rivaldo", "FW", 96, "Decisivo"), p("Roberto Carlos", "DF", 94, "Lateral foguete"), p("Cafu", "DF", 93, "Motor eterno"), p("Lúcio", "DF", 91, "Zagueiro líder"), p("Edmílson", "DF", 88, "Versátil"), p("Gilberto Silva", "MF", 89, "Proteção"), p("Kléberson", "MF", 87, "Surpresa"), p("Marcos", "GK", 90, "Muralha") ]},
    { nation: "Argentina", flag: "🇦🇷", year: 1986, aura: "camisa 10 absoluto", players: [
      p("Maradona", "MF", 99, "Gênio total"), p("Valdano", "FW", 92, "Atacante técnico"), p("Burruchaga", "MF", 90, "Chegada decisiva"), p("Ruggeri", "DF", 90, "Zagueiro campeão"), p("Pumpido", "GK", 87, "Goleiro campeão"), p("Giusti", "MF", 86, "Combate"), p("Olarticoechea", "DF", 86, "Lateral"), p("Brown", "DF", 88, "Raça"), p("Enrique", "MF", 85, "Motor"), p("Batista", "MF", 86, "Volante") ]},
    { nation: "Argentina", flag: "🇦🇷", year: 2022, aura: "energia e liderança", players: [
      p("Messi", "FW", 98, "Maestro decisivo"), p("Di María", "FW", 92, "Final de cinema"), p("J. Álvarez", "FW", 90, "Pressão e gol"), p("Mac Allister", "MF", 88, "Conector"), p("De Paul", "MF", 88, "Motor"), p("Enzo", "MF", 89, "Passe vertical"), p("Otamendi", "DF", 88, "Experiência"), p("Romero", "DF", 89, "Combate"), p("Molina", "DF", 86, "Apoio"), p("E. Martínez", "GK", 91, "Pênaltis") ]},
    { nation: "França", flag: "🇫🇷", year: 1998, aura: "casa, físico e técnica", players: [
      p("Zidane", "MF", 97, "Elegância"), p("Henry", "FW", 90, "Velocidade"), p("Trezeguet", "FW", 89, "Área"), p("Deschamps", "MF", 90, "Capitão"), p("Vieira", "MF", 91, "Força"), p("Thuram", "DF", 94, "Muralha"), p("Blanc", "DF", 91, "Classe"), p("Desailly", "DF", 92, "Potência"), p("Lizarazu", "DF", 89, "Lateral"), p("Barthez", "GK", 90, "Reflexos") ]},
    { nation: "França", flag: "🇫🇷", year: 2018, aura: "transição mortal", players: [
      p("Mbappé", "FW", 95, "Velocidade absurda"), p("Griezmann", "FW", 92, "Decisão"), p("Giroud", "FW", 88, "Pivô"), p("Pogba", "MF", 91, "Passe e força"), p("Kanté", "MF", 94, "Onipresente"), p("Matuidi", "MF", 87, "Trabalho"), p("Varane", "DF", 91, "Zagueiro elite"), p("Umtiti", "DF", 89, "Impulsão"), p("Pavard", "DF", 86, "Lateral"), p("Lloris", "GK", 90, "Capitão") ]},
    { nation: "Alemanha", flag: "🇩🇪", year: 2014, aura: "máquina coletiva", players: [
      p("Neuer", "GK", 96, "Goleiro-líbero"), p("Lahm", "DF", 94, "Precisão"), p("Hummels", "DF", 91, "Zagueiro técnico"), p("Boateng", "DF", 90, "Físico"), p("Kroos", "MF", 93, "Passe perfeito"), p("Schweinsteiger", "MF", 92, "Comando"), p("Özil", "MF", 90, "Visão"), p("Müller", "FW", 92, "Espaço"), p("Klose", "FW", 90, "Recordista"), p("Götze", "FW", 88, "Final") ]},
    { nation: "Itália", flag: "🇮🇹", year: 2006, aura: "defesa e frieza", players: [
      p("Buffon", "GK", 97, "Muralha"), p("Cannavaro", "DF", 97, "Bola de Ouro"), p("Nesta", "DF", 91, "Classe"), p("Zambrotta", "DF", 91, "Lateral total"), p("Pirlo", "MF", 95, "Regista"), p("Gattuso", "MF", 90, "Cão de guarda"), p("Totti", "MF", 92, "Criador"), p("Del Piero", "FW", 90, "Técnica"), p("Toni", "FW", 89, "Área"), p("Grosso", "DF", 88, "Momento") ]},
    { nation: "Espanha", flag: "🇪🇸", year: 2010, aura: "posse hipnótica", players: [
      p("Casillas", "GK", 94, "Santo"), p("Puyol", "DF", 93, "Raça"), p("Piqué", "DF", 91, "Saída"), p("Sergio Ramos", "DF", 92, "Potência"), p("Xavi", "MF", 97, "Controle"), p("Iniesta", "MF", 96, "Magia"), p("Busquets", "MF", 92, "Leitura"), p("Xabi Alonso", "MF", 91, "Passe longo"), p("David Villa", "FW", 94, "Gol"), p("Torres", "FW", 88, "Explosão") ]},
    { nation: "Portugal", flag: "🇵🇹", year: 2006, aura: "ponta e maestro", players: [
      p("Cristiano Ronaldo", "FW", 94, "Explosão"), p("Figo", "MF", 92, "Classe"), p("Deco", "MF", 91, "Criação"), p("Pauleta", "FW", 88, "Área"), p("Maniche", "MF", 88, "Chute"), p("Costinha", "MF", 86, "Volante"), p("Ricardo Carvalho", "DF", 91, "Elegância"), p("Nuno Valente", "DF", 86, "Lateral"), p("Miguel", "DF", 86, "Apoio"), p("Ricardo", "GK", 88, "Pênaltis") ]},
    { nation: "Holanda", flag: "🇳🇱", year: 1974, aura: "futebol total", players: [
      p("Cruyff", "FW", 98, "Futebol total"), p("Neeskens", "MF", 94, "Motor"), p("Rep", "FW", 88, "Ataque"), p("Rensenbrink", "FW", 90, "Técnica"), p("Krol", "DF", 92, "Líbero"), p("Haan", "MF", 89, "Versátil"), p("Jansen", "MF", 87, "Controle"), p("Suurbier", "DF", 87, "Lateral"), p("Rijsbergen", "DF", 86, "Zagueiro"), p("Jongbloed", "GK", 85, "Goleiro") ]},
    { nation: "Inglaterra", flag: "🏴", year: 1966, aura: "casa e tradição", players: [
      p("Bobby Charlton", "MF", 96, "Lenda"), p("Bobby Moore", "DF", 96, "Capitão"), p("Gordon Banks", "GK", 94, "Reflexos"), p("Geoff Hurst", "FW", 91, "Final"), p("Martin Peters", "MF", 89, "Chegada"), p("Nobby Stiles", "MF", 87, "Marcação"), p("Jack Charlton", "DF", 88, "Zagueiro"), p("Alan Ball", "MF", 88, "Motor"), p("Roger Hunt", "FW", 88, "Área"), p("Ray Wilson", "DF", 86, "Lateral") ]},
  ];

  const opponents = ["Uruguai 1950", "Brasil 1970", "Itália 1982", "Argentina 1986", "Alemanha 1990", "França 1998", "Brasil 2002", "Itália 2006", "Espanha 2010", "Alemanha 2014", "França 2018", "Argentina 2022", "Croácia 2018", "Holanda 2010", "Portugal 2006", "Bélgica 2018"];
  const stages = ["Grupo 1", "Grupo 2", "Grupo 3", "Oitavas", "Quartas", "Semifinal", "Final"];

  const state = {
    formation: "4-3-3",
    mode: "classic",
    tactic: "balanced",
    lineup: [],
    currentSquad: null,
    usedSquads: new Set(),
    skips: 3,
    finished: false,
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

  function p(name, role, rating, trait) { return { name, role, rating, trait }; }
  function normalizeRole(slot) {
    if (slot === "GK") return "GK";
    if (["CB", "LB", "RB"].includes(slot)) return "DF";
    if (["CM", "DM", "AM", "LM", "RM"].includes(slot)) return "MF";
    return "FW";
  }
  function initials(name) { return name.split(/\s+/).map(x => x[0]).join("").slice(0, 2).toUpperCase(); }
  function availableSlotsFor(player) {
    return state.lineup.filter(slot => !slot.player && normalizeRole(slot.pos) === player.role);
  }
  function flattenFormation() {
    return formations[state.formation].map((row, rowIndex) => row.map((pos, slotIndex) => ({ pos, row: rowIndex, slotIndex, player: null }))).flat();
  }
  function groupedLineup() {
    const rows = formations[state.formation].length;
    return Array.from({ length: rows }, (_, i) => state.lineup.filter(slot => slot.row === i));
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
        name.textContent = slot.player ? slot.player.name : "Vaga aberta";
        const meta = document.createElement("div");
        meta.className = "slot-meta";
        meta.textContent = slot.player ? `${slot.player.nation} ${slot.player.year} · ${slot.player.trait}` : roleLabel(normalizeRole(slot.pos));
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

  function roleLabel(role) {
    return { GK: "Goleiro", DF: "Defesa", MF: "Meio", FW: "Ataque" }[role] || role;
  }

  function updateStats() {
    const players = state.lineup.map(s => s.player).filter(Boolean);
    if (!players.length) {
      overallStat.textContent = "OVR --";
      chemStat.textContent = "QUI --";
      simulateBtn.disabled = true;
      return;
    }
    const overall = Math.round(players.reduce((sum, p) => sum + p.rating, 0) / players.length);
    const chemistry = calculateChemistry(players);
    overallStat.textContent = `OVR ${overall}`;
    chemStat.textContent = `QUI ${chemistry}`;
    simulateBtn.disabled = players.length !== state.lineup.length;
  }

  function calculateChemistry(players) {
    const nations = new Map();
    const eras = new Map();
    players.forEach(player => {
      nations.set(player.nation, (nations.get(player.nation) || 0) + 1);
      eras.set(Math.floor(player.year / 10) * 10, (eras.get(Math.floor(player.year / 10) * 10) || 0) + 1);
    });
    const nationBonus = Math.max(...nations.values(), 0) * 3;
    const eraBonus = Math.max(...eras.values(), 0) * 2;
    const balance = ["GK", "DF", "MF", "FW"].every(role => players.some(p => p.role === role)) ? 12 : 0;
    return Math.min(100, 48 + nationBonus + eraBonus + balance + players.length * 2);
  }

  function rollSquad() {
    if (state.finished) return;
    rollBtn.classList.add("rolling");
    setTimeout(() => rollBtn.classList.remove("rolling"), 650);
    const remaining = squads.filter((_, index) => !state.usedSquads.has(index));
    const pool = remaining.length ? remaining : squads;
    const squad = pool[Math.floor(Math.random() * pool.length)];
    const index = squads.indexOf(squad);
    state.usedSquads.add(index);
    state.currentSquad = squad;
    renderDraw(squad);
  }

  function renderDraw(squad) {
    rollTitle.textContent = `${squad.flag} ${squad.nation} ${squad.year}`;
    drawCard.className = "draw-card";
    drawCard.innerHTML = "";
    const title = document.createElement("h3");
    title.textContent = `${squad.flag} ${squad.nation} · Copa ${squad.year}`;
    const desc = document.createElement("p");
    desc.textContent = `Aura: ${squad.aura}. Escolha um jogador compatível com as vagas abertas.`;
    drawCard.append(title, desc);
    skipBtn.disabled = state.skips <= 0;
    renderPlayers(squad.players.map(player => ({ ...player, nation: squad.nation, year: squad.year, flag: squad.flag })));
  }

  function renderPlayers(players) {
    playerList.innerHTML = "";
    players.sort((a, b) => b.rating - a.rating).forEach(player => {
      const compatible = availableSlotsFor(player).length > 0;
      const btn = document.createElement("button");
      btn.className = "player-card";
      btn.type = "button";
      btn.disabled = !compatible;
      const avatar = document.createElement("span");
      avatar.className = "avatar";
      avatar.textContent = initials(player.name);
      const copy = document.createElement("span");
      const name = document.createElement("span");
      name.className = "player-name";
      name.textContent = player.name;
      const detail = document.createElement("span");
      detail.className = "player-detail";
      detail.textContent = `${roleLabel(player.role)} · ${player.trait}${compatible ? "" : " · sem vaga compatível"}`;
      copy.append(name, detail);
      const rating = document.createElement("span");
      rating.className = "player-rating";
      rating.textContent = state.mode === "memory" ? "?" : player.rating;
      btn.append(avatar, copy, rating);
      btn.addEventListener("click", () => pickPlayer(player));
      playerList.appendChild(btn);
    });
  }

  function pickPlayer(player) {
    const open = availableSlotsFor(player);
    if (!open.length) return;
    open[0].player = player;
    state.currentSquad = null;
    rollTitle.textContent = "Jogador escalado";
    drawCard.className = "draw-card empty";
    drawCard.innerHTML = `<p>${escapeHtml(player.name)} entrou no time. Role novamente para buscar a próxima peça.</p>`;
    playerList.innerHTML = "";
    skipBtn.disabled = true;
    renderLineup();
    saveRunHistory();
  }

  function skipSquad() {
    if (state.skips <= 0 || !state.currentSquad) return;
    state.skips -= 1;
    skipCount.textContent = state.skips;
    state.currentSquad = null;
    skipBtn.disabled = true;
    drawCard.className = "draw-card empty";
    drawCard.innerHTML = "<p>Coringa usado. Role outra seleção.</p>";
    playerList.innerHTML = "";
  }

  function simulateTournament(auto = false) {
    const players = state.lineup.map(s => s.player).filter(Boolean);
    if (players.length !== state.lineup.length) return;
    simulationPanel.classList.remove("hidden");
    matchTimeline.innerHTML = "";
    resultCard.classList.add("hidden");
    const overall = Math.round(players.reduce((sum, p) => sum + p.rating, 0) / players.length);
    const chemistry = calculateChemistry(players);
    const strength = overall + chemistry * .16 + tacticBonus();
    const matches = buildCampaign(strength, players);
    const delay = auto ? 40 : 520;
    let index = 0;
    function next() {
      if (index >= matches.length) return finishCampaign(matches, overall, chemistry);
      renderMatch(matches[index]);
      index += 1;
      setTimeout(next, delay);
    }
    next();
  }

  function tacticBonus() {
    if (state.tactic === "attack") return 2.5;
    if (state.tactic === "control") return 1.5;
    return 2;
  }

  function buildCampaign(strength, players) {
    const shuffled = [...opponents].sort(() => Math.random() - .5);
    const matches = [];
    let alive = true;
    for (let i = 0; i < stages.length && alive; i++) {
      const opponent = shuffled[i % shuffled.length];
      const opponentPower = 82 + Math.random() * 16 + (i > 2 ? i * 1.7 : 0);
      const diff = strength - opponentPower;
      const ourGoals = clamp(Math.round(1.6 + diff / 8 + Math.random() * 2.7), 0, 8);
      const theirGoals = clamp(Math.round(1.2 - diff / 12 + Math.random() * 2.1), 0, 5);
      let win = ourGoals > theirGoals;
      let penalties = false;
      let finalOur = ourGoals;
      let finalTheir = theirGoals;
      if (i > 2 && ourGoals === theirGoals) {
        penalties = true;
        win = Math.random() < .52 + diff / 80;
        finalOur = ourGoals;
        finalTheir = theirGoals;
      }
      if (i <= 2 && matches.filter(m => m.win).length + (win ? 1 : 0) < Math.max(0, i - 1)) alive = false;
      if (i > 2 && !win) alive = false;
      matches.push({ stage: stages[i], opponent, ourGoals: finalOur, theirGoals: finalTheir, win, penalties, scorers: pickScorers(players, finalOur), sevenZero: finalOur >= 7 && finalTheir === 0 });
    }
    return matches;
  }

  function renderMatch(match) {
    const card = document.createElement("div");
    card.className = "match-card";
    const left = document.createElement("div");
    left.innerHTML = `<div class="match-stage">${escapeHtml(match.stage)}${match.penalties ? " · pênaltis" : ""}</div><strong>Agente Fino FC x ${escapeHtml(match.opponent)}</strong><div class="scorers">${match.scorers.length ? `Gols: ${match.scorers.map(escapeHtml).join(", ")}` : "Jogo travado, sem gols do nosso lado."}</div>`;
    const score = document.createElement("div");
    score.className = "match-score";
    score.textContent = `${match.ourGoals}–${match.theirGoals}`;
    card.append(left, score);
    matchTimeline.appendChild(card);
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function finishCampaign(matches, overall, chemistry) {
    const wins = matches.filter(m => m.win).length;
    const goalsFor = matches.reduce((sum, m) => sum + m.ourGoals, 0);
    const goalsAgainst = matches.reduce((sum, m) => sum + m.theirGoals, 0);
    const sevenZero = matches.some(m => m.sevenZero);
    const champion = wins >= 7;
    resultCard.className = "result-card";
    resultCard.innerHTML = `
      <p class="eyebrow">Resultado final</p>
      <h3>${champion ? "Campeão da Copa dos Sonhos" : wins >= 5 ? "Campanha pesada" : "Eliminação dolorida"}</h3>
      <p>${sevenZero ? "Você conseguiu o placar mítico: 7x0 ou mais sem sofrer gol." : "Ainda não veio o 7x0 perfeito. Ajuste a formação, química e tente outra vez."}</p>
      <div class="result-grid">
        <div class="result-stat"><strong>${wins}</strong><span>vitórias</span></div>
        <div class="result-stat"><strong>${goalsFor}</strong><span>gols pró</span></div>
        <div class="result-stat"><strong>${goalsAgainst}</strong><span>gols contra</span></div>
        <div class="result-stat"><strong>${overall}/${chemistry}</strong><span>OVR/QUI</span></div>
      </div>`;
    state.finished = true;
    saveRunHistory({ wins, goalsFor, goalsAgainst, sevenZero, champion });
  }

  function pickScorers(players, goals) {
    const attackers = players.filter(p => p.role === "FW");
    const creators = players.filter(p => p.role === "MF");
    const pool = [...attackers, ...attackers, ...creators, ...players];
    return Array.from({ length: goals }, () => pool[Math.floor(Math.random() * pool.length)]?.name || "Gol contra");
  }

  function resetGame() {
    state.lineup = flattenFormation();
    state.currentSquad = null;
    state.usedSquads = new Set();
    state.skips = 3;
    state.finished = false;
    skipCount.textContent = "3";
    rollTitle.textContent = "Role o dado";
    drawCard.className = "draw-card empty";
    drawCard.innerHTML = "<p>Uma seleção histórica vai aparecer aqui. Escolha um jogador compatível com as vagas abertas.</p>";
    playerList.innerHTML = "";
    matchTimeline.innerHTML = "";
    simulationPanel.classList.add("hidden");
    resultCard.classList.add("hidden");
    skipBtn.disabled = true;
    renderLineup();
  }

  function setFormation(value) {
    if (!formations[value]) return;
    state.formation = value;
    document.querySelectorAll("[data-formation]").forEach(btn => btn.classList.toggle("active", btn.dataset.formation === value));
    resetGame();
  }
  function setMode(value) {
    state.mode = value;
    document.querySelectorAll("[data-mode]").forEach(btn => btn.classList.toggle("active", btn.dataset.mode === value));
    if (state.currentSquad) renderDraw(state.currentSquad);
    renderLineup();
  }
  function setTactic(value) {
    state.tactic = value;
    document.querySelectorAll("[data-tactic]").forEach(btn => btn.classList.toggle("active", btn.dataset.tactic === value));
  }

  function saveRunHistory(result = null) {
    const players = state.lineup.map(s => s.player).filter(Boolean).length;
    const item = { at: new Date().toISOString(), formation: state.formation, players, result };
    try {
      const current = JSON.parse(localStorage.getItem("agente_fino_dream_cup_history") || "[]");
      current.unshift(item);
      localStorage.setItem("agente_fino_dream_cup_history", JSON.stringify(current.slice(0, 50)));
    } catch (_) {}
  }

  function clamp(value, min, max) { return Math.max(min, Math.min(max, value)); }
  function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch])); }

  document.querySelectorAll("[data-formation]").forEach(btn => btn.addEventListener("click", () => setFormation(btn.dataset.formation)));
  document.querySelectorAll("[data-mode]").forEach(btn => btn.addEventListener("click", () => setMode(btn.dataset.mode)));
  document.querySelectorAll("[data-tactic]").forEach(btn => btn.addEventListener("click", () => setTactic(btn.dataset.tactic)));
  rollBtn.addEventListener("click", rollSquad);
  skipBtn.addEventListener("click", skipSquad);
  resetBtn.addEventListener("click", resetGame);
  simulateBtn.addEventListener("click", () => simulateTournament(false));
  quickSimBtn.addEventListener("click", () => simulateTournament(true));

  resetGame();
})();
