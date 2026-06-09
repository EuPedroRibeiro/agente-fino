(() => {
  "use strict";

  const FORMATIONS = {
    "4-3-3": [["LW", "ST", "RW"], ["CM", "AM", "CM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-4-2": [["ST", "ST"], ["LM", "CM", "CM", "RM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "4-2-3-1": [["ST"], ["LW", "AM", "RW"], ["DM", "DM"], ["LB", "CB", "CB", "RB"], ["GK"]],
    "3-5-2": [["ST", "ST"], ["LM", "CM", "AM", "CM", "RM"], ["CB", "CB", "CB"], ["GK"]],
  };
  const GROUP_STAGES = ["Grupo 1", "Grupo 2", "Grupo 3"];
  const KNOCKOUT_STAGES = ["Oitavas", "Quartas", "Semifinal", "Final"];
  const OPPONENT_RANGES = [[76, 84], [78, 86], [80, 88], [84, 90], [87, 93], [90, 96], [92, 98]];
  const PROGRESS_KEY = "dream_cup_progress_v1";
  const RUN_HISTORY_KEY = "dream_cup_run_history_v1";
  const POSITION_ICONS = { GK: "▣", DF: "◆", MF: "✦", FW: "⚡" };
  const ACTIONS = {
    BOOT_GAME: "BOOT_GAME",
    START_RUN: "START_RUN",
    ROLL_SQUAD: "ROLL_SQUAD",
    SKIP_SQUAD: "SKIP_SQUAD",
    PICK_PLAYER: "PICK_PLAYER",
    SELECT_FIELD_CARD: "SELECT_FIELD_CARD",
    MOVE_PLAYER: "MOVE_PLAYER",
    SWAP_PLAYERS: "SWAP_PLAYERS",
    CANCEL_MOVE: "CANCEL_MOVE",
    START_CAMPAIGN: "START_CAMPAIGN",
    SIMULATE_NEXT_MATCH: "SIMULATE_NEXT_MATCH",
    FINISH_CAMPAIGN: "FINISH_CAMPAIGN",
    RESET_RUN: "RESET_RUN",
  };

  const normalizeText = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const roleLabel = (role) => ({ GK: "Goleiro", DF: "Defensor", MF: "Meio-campista", FW: "Atacante" }[role] || "Jogador");
  const roleBySlot = (slot) => slot === "GK" ? "GK" : ["CB", "LB", "RB"].includes(slot) ? "DF" : ["CM", "DM", "AM", "LM", "RM"].includes(slot) ? "MF" : "FW";
  const playerKey = (player) => `${player.id || player.name}-${player.nation || ""}-${player.year || ""}`;
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
  const seededNumber = (seed) => {
    let value = Number(seed || 1) % 2147483647;
    if (value <= 0) value += 2147483646;
    value = value * 16807 % 2147483647;
    return (value - 1) / 2147483646;
  };

  function flattenFormation(formation = "4-3-3") {
    return FORMATIONS[formation].flatMap((row, rowIndex) => row.map((pos, slotIndex) => ({ pos, row: rowIndex, slotIndex, player: null })));
  }

  function compatibleSlotsForPlayer(player) {
    const name = normalizeText(player.name);
    const position = normalizeText(`${player.position_code || ""} ${player.position_name || ""}`);
    const trait = normalizeText(`${player.trait || ""} ${player.trait_label || ""}`);
    if (player.role === "GK") return ["GK"];
    if (name.includes("roberto carlos")) return ["LB", "LM"];
    if (name.includes("cafu")) return ["RB", "RM"];
    if (name === "ronaldo") return ["ST"];
    if (name.includes("rivaldo")) return ["AM", "LW", "ST"];
    if (name.includes("ze roberto")) return ["CM", "LM", "LB"];
    if (position.includes("centre back") || position.includes("center back") || position.includes("zagueir")) return ["CB"];
    if (position.includes("left back") || position.includes("lateral esquer")) return ["LB", "LM"];
    if (position.includes("right back") || position.includes("lateral direit")) return ["RB", "RM"];
    if (position.includes("defensive midfielder") || trait.includes("volante")) return ["DM", "CM"];
    if (position.includes("attacking midfielder") || position.includes("playmaker") || trait.includes("maestro")) return ["AM", "CM"];
    if (position.includes("wide midfielder")) return ["LM", "RM", "LW", "RW"];
    if (position.includes("wing")) return ["LW", "RW"];
    if (position.includes("striker") || position.includes("forward central")) return ["ST"];
    if (player.role === "DF") return ["CB", "LB", "RB"];
    if (player.role === "MF") return ["CM", "DM", "AM"];
    return ["ST", "LW", "RW"];
  }

  function preferredSlotsForPlayer(player) {
    const slots = compatibleSlotsForPlayer(player);
    if (player.role === "DF" && slots.length === 3) return ["CB"];
    if (player.role === "MF" && slots.includes("CM")) return ["CM"];
    if (player.role === "FW" && slots.includes("ST")) return ["ST"];
    return slots.slice(0, 1);
  }

  function slotCompatibilityScore(player, slot) {
    if (!player || !slot) return 0;
    if (preferredSlotsForPlayer(player).includes(slot)) return 1;
    if (compatibleSlotsForPlayer(player).includes(slot)) return 0.8;
    if (roleBySlot(slot) === player.role) return 0.55;
    return 0;
  }

  function positionMetrics(lineup) {
    const filled = lineup.filter((slot) => slot.player);
    if (!filled.length) return { fit: 0, fitPercent: 0, natural: 0, secondary: 0, improvised: 0, incompatible: 0 };
    const scores = filled.map((slot) => slotCompatibilityScore(slot.player, slot.pos));
    return {
      fit: scores.reduce((sum, score) => sum + score, 0) / scores.length,
      fitPercent: Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length * 100),
      natural: scores.filter((score) => score === 1).length,
      secondary: scores.filter((score) => score === 0.8).length,
      improvised: scores.filter((score) => score === 0.55).length,
      incompatible: scores.filter((score) => score === 0).length,
    };
  }

  function lineupOverall(lineup) {
    const players = lineup.filter((slot) => slot.player).map((slot) => slot.player);
    return players.length ? players.reduce((sum, player) => sum + Number(player.rating || 70), 0) / players.length : 0;
  }

  function lineupChemistry(lineup) {
    const players = lineup.filter((slot) => slot.player).map((slot) => slot.player);
    if (!players.length) return 0;
    const nations = new Map();
    const decades = new Map();
    players.forEach((player) => {
      nations.set(player.nation || "?", (nations.get(player.nation || "?") || 0) + 1);
      const decade = Math.floor(Number(player.year || 0) / 10) * 10;
      decades.set(decade, (decades.get(decade) || 0) + 1);
    });
    const sameNation = Math.max(...nations.values());
    const sameDecade = Math.max(...decades.values());
    const diversityPenalty = Math.max(0, nations.size - 4) * 5;
    return clamp(Math.round(28 + sameNation * 5 + sameDecade * 3 + players.length * 2 - diversityPenalty), 10, 100);
  }

  function tacticBonus(tactic, overall, chemistry, fitPercent) {
    if (tactic === "attack") return overall >= 88 && fitPercent >= 80 ? 3 : -4;
    if (tactic === "control") return chemistry >= 72 ? 3 : -3;
    return chemistry >= 55 && fitPercent >= 65 ? 1.5 : 0;
  }

  function calculateTeamPower(lineup, tactic = "balanced", randomVariance = 0) {
    const overall = lineupOverall(lineup);
    const chemistry = lineupChemistry(lineup);
    const metrics = positionMetrics(lineup);
    const starBonus = Math.min(3, lineup.filter((slot) => Number(slot.player?.rating || 0) >= 90).length * 0.6);
    const lowChemPenalty = chemistry < 50 ? (50 - chemistry) * 0.5 : 0;
    const badFitPenalty = metrics.fitPercent < 70 ? (70 - metrics.fitPercent) * 0.42 : 0;
    const incompletePenalty = Math.max(0, 11 - lineup.filter((slot) => slot.player).length) * 4;
    return Number((
      overall * 0.52 +
      chemistry * 0.22 +
      metrics.fitPercent * 0.20 +
      tacticBonus(tactic, overall, chemistry, metrics.fitPercent) +
      starBonus -
      lowChemPenalty -
      badFitPenalty -
      incompletePenalty +
      randomVariance
    ).toFixed(2));
  }

  function calculateOpponentPower(stageIndex, randomValue = Math.random()) {
    const [min, max] = OPPONENT_RANGES[Math.min(stageIndex, OPPONENT_RANGES.length - 1)];
    return Number((min + (max - min) * randomValue).toFixed(2));
  }

  function calculateMatchOdds(teamPower, opponentPower) {
    const win = clamp(1 / (1 + Math.exp(-(teamPower - opponentPower) / 7)), 0.05, 0.9);
    const draw = clamp(0.28 - Math.abs(teamPower - opponentPower) * 0.012, 0.08, 0.28);
    return { win: Number(win.toFixed(3)), draw: Number(draw.toFixed(3)), loss: Number((1 - win - draw).toFixed(3)) };
  }

  function simulateScore(lineup, tactic, opponentPower, stageIndex, randomValue = Math.random(), knockout = false) {
    const overall = lineupOverall(lineup);
    const chemistry = lineupChemistry(lineup);
    const metrics = positionMetrics(lineup);
    const variance = (randomValue - 0.5) * 8;
    const teamPower = calculateTeamPower(lineup, tactic, variance);
    const pressure = knockout ? Math.max(0, stageIndex - 2) * 1.2 : 0;
    const difference = teamPower - opponentPower - pressure;
    const attackExpected = clamp(1.15 + difference / 11, 0.12, 4.8);
    const defenseExpected = clamp(1.15 - difference / 11, 0.12, 4.8);
    let goalsFor = clamp(Math.floor(attackExpected * (0.48 + randomValue * 0.92)), 0, 6);
    let goalsAgainst = clamp(Math.floor(defenseExpected * (1.38 - randomValue * 0.82)), 0, 6);
    const canSeven = overall >= 88 && chemistry >= 70 && metrics.fitPercent >= 80 && difference >= 12 && randomValue > 0.995;
    if (canSeven) {
      goalsFor = 7;
      goalsAgainst = 0;
    }
    if (knockout && goalsFor === goalsAgainst) {
      if (difference > 2 && randomValue >= 0.5) goalsFor += 1;
      else goalsAgainst += 1;
    }
    return {
      goalsFor,
      goalsAgainst,
      teamPower,
      opponentPower,
      odds: calculateMatchOdds(teamPower, opponentPower),
      sevenZero: goalsFor === 7 && goalsAgainst === 0,
    };
  }

  function simulateMatch(lineup, tactic, opponentPower, stageIndex, randomValue = Math.random(), knockout = false) {
    return simulateScore(lineup, tactic, opponentPower, stageIndex, randomValue, knockout);
  }

  function calculateGroupTable(matches) {
    return matches.reduce((table, match) => {
      table.played += 1;
      table.goalsFor += match.goalsFor;
      table.goalsAgainst += match.goalsAgainst;
      if (match.goalsFor > match.goalsAgainst) {
        table.wins += 1;
        table.points += 3;
      } else if (match.goalsFor === match.goalsAgainst) {
        table.draws += 1;
        table.points += 1;
      } else table.losses += 1;
      table.balance = table.goalsFor - table.goalsAgainst;
      return table;
    }, { played: 0, wins: 0, draws: 0, losses: 0, goalsFor: 0, goalsAgainst: 0, balance: 0, points: 0 });
  }

  function determineGroupQualification(table, randomValue = Math.random()) {
    if (table.points >= 4) return true;
    if (table.points === 3 && table.balance >= 0) return true;
    if (table.points === 3 && table.balance < 0) return randomValue > 0.9;
    return false;
  }

  function opponentFor(stateLike, stageIndex, randomValue) {
    const squads = Array.isArray(stateLike?.squads) ? stateLike.squads.filter((squad) => Array.isArray(squad.players) && squad.players.length >= 15) : [];
    const squad = squads.length ? squads[Math.floor(randomValue * squads.length) % squads.length] : null;
    return { name: squad ? `${squad.nation} ${squad.year}` : `Adversário histórico ${stageIndex + 1}`, power: calculateOpponentPower(stageIndex, randomValue) };
  }

  function simulateGroupStage(lineup, tactic = "balanced", options = {}) {
    const randomValues = options.randomValues || [0.42, 0.58, 0.36];
    const matches = GROUP_STAGES.map((stage, index) => {
      const randomValue = randomValues[index] ?? seededNumber((options.runSeed || 1) + index);
      const opponentPower = options.opponentPowers?.[index] ?? calculateOpponentPower(index, 0.35 + randomValue * 0.55);
      const result = simulateScore(lineup, tactic, opponentPower, index, randomValue, false);
      return { stage, opponent: options.opponents?.[index] || `Adversário do grupo ${index + 1}`, ...result };
    });
    const table = calculateGroupTable(matches);
    const qualified = determineGroupQualification(table, options.qualificationRandom ?? randomValues[2] ?? 0.5);
    return { matches, table, qualified, sevenZero: matches.some((match) => match.sevenZero) };
  }

  function simulateKnockout(lineup, tactic = "balanced", options = {}) {
    const matches = [];
    let sevenZero = false;
    for (let index = 0; index < KNOCKOUT_STAGES.length; index += 1) {
      const stageIndex = index + 3;
      const randomValue = options.randomValues?.[index] ?? seededNumber((options.runSeed || 11) + index);
      const opponentPower = options.opponentPowers?.[index] ?? calculateOpponentPower(stageIndex, 0.45 + randomValue * 0.5);
      const result = simulateScore(lineup, tactic, opponentPower, stageIndex, randomValue, true);
      const match = { stage: KNOCKOUT_STAGES[index], opponent: options.opponents?.[index] || `Adversário das ${KNOCKOUT_STAGES[index]}`, ...result };
      matches.push(match);
      sevenZero ||= match.sevenZero;
      if (match.goalsFor < match.goalsAgainst) break;
    }
    return { matches, sevenZero };
  }

  function resultReason(lineup, campaign) {
    const chemistry = lineupChemistry(lineup);
    const fit = positionMetrics(lineup).fitPercent;
    const overall = lineupOverall(lineup);
    if (chemistry < 50) return "A química baixa desmontou o time nos momentos decisivos.";
    if (fit < 70) return "O encaixe tático ruim cobrou caro.";
    if (overall < 80) return "O elenco lutou, mas faltou força para enfrentar os gigantes.";
    const last = campaign.matches[campaign.matches.length - 1];
    if (last && last.opponentPower > last.teamPower) return "O adversário foi mais forte no confronto decisivo.";
    return "A margem foi pequena e a Copa decidiu nos detalhes.";
  }

  function simulateCampaign(lineup, tactic = "balanced", options = {}) {
    const group = simulateGroupStage(lineup, tactic, options.group || options);
    if (!group.qualified) {
      return {
        matches: group.matches,
        groupTable: group.table,
        qualified: false,
        sevenZero: group.sevenZero,
        result: { code: "group", title: "Caiu na fase de grupos.", reason: resultReason(lineup, { matches: group.matches }) },
      };
    }
    const knockout = simulateKnockout(lineup, tactic, options.knockout || options);
    const matches = [...group.matches, ...knockout.matches];
    const last = knockout.matches[knockout.matches.length - 1];
    const won = knockout.matches.length === 4 && last.goalsFor > last.goalsAgainst;
    let result;
    if (won) result = { code: "champion", title: "Campeão dos sonhos.", reason: "Força, química e encaixe sobreviveram à campanha inteira." };
    else if (last.stage === "Final") result = { code: "runner_up", title: "Vice-campeão.", reason: resultReason(lineup, { matches }) };
    else result = { code: normalizeText(last.stage), title: `Caiu em ${last.stage}.`, reason: resultReason(lineup, { matches }) };
    return { matches, groupTable: group.table, qualified: true, sevenZero: group.sevenZero || knockout.sevenZero, result };
  }

  function matchOutcome(match) {
    if (match.goalsFor > match.goalsAgainst) return "win";
    if (match.goalsFor === match.goalsAgainst) return "draw";
    return "loss";
  }

  function buildFinishedRun(gameState) {
    const campaign = gameState.campaign || { matches: [], groupTable: {} };
    const groupTable = campaign.groupTable || {};
    const matches = (campaign.matches || []).map((match) => ({
      stage: match.stage,
      opponent: match.opponent,
      opponentPower: Number(match.opponentPower || 0),
      teamPower: Number(match.teamPower || 0),
      goalsFor: Number(match.goalsFor || 0),
      goalsAgainst: Number(match.goalsAgainst || 0),
      outcome: matchOutcome(match),
      sevenZero: Boolean(match.sevenZero),
    }));
    const goalsFor = matches.reduce((sum, match) => sum + match.goalsFor, 0);
    const goalsAgainst = matches.reduce((sum, match) => sum + match.goalsAgainst, 0);
    return {
      id: `run-${gameState.runSeed}-${Date.now()}`,
      createdAt: new Date().toISOString(),
      result: { ...(gameState.result || campaign.result || {}) },
      stats: {
        overall: Number(gameState.stats?.overall || Math.round(lineupOverall(gameState.lineup))),
        chemistry: Number(gameState.stats?.chemistry || lineupChemistry(gameState.lineup)),
        fit: Number(gameState.stats?.fit || positionMetrics(gameState.lineup).fitPercent),
        points: Number(groupTable.points || 0),
        balance: goalsFor - goalsAgainst,
        goalsFor,
        goalsAgainst,
      },
      lineup: gameState.lineup.filter((slot) => slot.player).map((slot) => ({
        slot: slot.pos,
        name: slot.player.name,
        nation: slot.player.nation,
        year: slot.player.year,
        rating: Number(slot.player.rating || 0),
        role_label: slot.player.role_label || roleLabel(slot.player.role),
        shirt_number: slot.player.shirt_number || null,
        trait_label: slot.player.trait_label || roleLabel(slot.player.role),
        fitScore: slotCompatibilityScore(slot.player, slot.pos),
      })),
      matches,
      sevenZero: Boolean(campaign.sevenZero),
      reason: gameState.result?.reason || campaign.result?.reason || "",
    };
  }

  function mergeRunHistory(history, run) {
    if (!run) return Array.isArray(history) ? history.slice(0, 10) : [];
    return [run, ...(Array.isArray(history) ? history.filter((item) => item?.id !== run.id) : [])].slice(0, 10);
  }

  function emptyProgress() {
    return { runs: 0, bestCampaign: "Nenhuma", highestOverall: 0, highestChemistry: 0, highestFit: 0, sevenZeroFound: false, titles: 0, achievements: [] };
  }

  function createGameState(overrides = {}) {
    const formation = overrides.formation || "4-3-3";
    return {
      phase: "boot",
      database: null,
      squads: [],
      currentSquad: null,
      draftLocked: false,
      skipsLeft: 3,
      lineup: flattenFormation(formation),
      selectedSlot: null,
      selectedPlayer: null,
      campaign: null,
      result: null,
      finishedRun: null,
      runHistory: [],
      selectedReportRun: null,
      activeResultTab: "result",
      achievements: [],
      stats: { overall: 0, chemistry: 0, fit: 0 },
      runSeed: Date.now(),
      formation,
      mode: "classic",
      tactic: "balanced",
      usedSquadIds: new Set(),
      filter: "",
      notice: "Role uma seleção para começar o draft.",
      progress: emptyProgress(),
      ...overrides,
    };
  }

  const state = createGameState();

  function chosenPlayerKeys(gameState) {
    return new Set(gameState.lineup.filter((slot) => slot.player).map((slot) => playerKey(slot.player)));
  }

  function availableSlotsFor(gameState, player) {
    return gameState.lineup.filter((slot) => !slot.player && slotCompatibilityScore(player, slot.pos) >= 0.8);
  }

  function refreshStats(gameState) {
    gameState.stats = {
      overall: Math.round(lineupOverall(gameState.lineup)),
      chemistry: lineupChemistry(gameState.lineup),
      fit: positionMetrics(gameState.lineup).fitPercent,
    };
  }

  function randomSquad(gameState) {
    const candidates = gameState.squads.filter((squad) => !gameState.usedSquadIds.has(squad.id));
    return candidates.length ? candidates[Math.floor(Math.random() * candidates.length)] : null;
  }

  function canMoveTo(gameState, sourceIndex, targetIndex) {
    const source = gameState.lineup[sourceIndex];
    const target = gameState.lineup[targetIndex];
    if (!source?.player || sourceIndex === targetIndex || slotCompatibilityScore(source.player, target?.pos) === 0) return false;
    return !target.player || slotCompatibilityScore(target.player, source.pos) > 0;
  }

  function applyAction(gameState, action) {
    const type = action?.type;
    if (!type) return false;
    if (type === ACTIONS.BOOT_GAME) {
      gameState.database = action.database || null;
      gameState.squads = Array.isArray(action.database?.squads) ? action.database.squads.filter((squad) => Array.isArray(squad.players) && squad.players.length) : [];
      gameState.phase = "draft";
      gameState.notice = "Role uma seleção para começar o draft.";
      return true;
    }
    if (type === ACTIONS.START_RUN || type === ACTIONS.RESET_RUN) {
      const progress = gameState.progress || emptyProgress();
      const runHistory = gameState.runHistory || [];
      const database = gameState.database;
      const squads = gameState.squads;
      const formation = action.formation || gameState.formation || "4-3-3";
      Object.assign(gameState, createGameState({ phase: "draft", database, squads, formation, mode: gameState.mode, tactic: gameState.tactic, progress, runHistory }));
      return true;
    }
    if (type === ACTIONS.ROLL_SQUAD) {
      if (!["draft", "lineup"].includes(gameState.phase) || gameState.draftLocked) return false;
      const squad = action.squad || randomSquad(gameState);
      if (!squad) {
        gameState.notice = "Não há mais elencos disponíveis nesta run.";
        return false;
      }
      gameState.usedSquadIds.add(squad.id);
      const picked = chosenPlayerKeys(gameState);
      const hasCompatible = squad.players.some((player) => availableSlotsFor(gameState, player).length && !picked.has(playerKey(player)));
      if (!hasCompatible) {
        gameState.currentSquad = null;
        gameState.draftLocked = false;
        gameState.notice = "Elenco sem opção compatível: novo sorteio liberado.";
        return true;
      }
      gameState.currentSquad = squad;
      gameState.draftLocked = true;
      gameState.phase = "draft";
      gameState.notice = gameState.skipsLeft > 0 ? "Escolha um jogador deste elenco ou use um coringa." : "Sem coringas: escolha alguém deste elenco.";
      return true;
    }
    if (type === ACTIONS.SKIP_SQUAD) {
      if (!gameState.draftLocked || !gameState.currentSquad || gameState.skipsLeft <= 0) return false;
      gameState.skipsLeft -= 1;
      gameState.currentSquad = null;
      gameState.draftLocked = false;
      gameState.notice = `Coringa usado. Restam ${gameState.skipsLeft}.`;
      return true;
    }
    if (type === ACTIONS.PICK_PLAYER) {
      if (!gameState.draftLocked || !gameState.currentSquad || !action.player) return false;
      const slots = availableSlotsFor(gameState, action.player);
      if (!slots.length || chosenPlayerKeys(gameState).has(playerKey(action.player))) return false;
      const preferred = preferredSlotsForPlayer(action.player);
      const target = slots.find((slot) => preferred.includes(slot.pos)) || slots[0];
      target.player = { ...action.player, nation: gameState.currentSquad.nation, year: gameState.currentSquad.year, tournament: gameState.currentSquad.tournament };
      gameState.currentSquad = null;
      gameState.draftLocked = false;
      gameState.selectedPlayer = null;
      gameState.phase = gameState.lineup.every((slot) => slot.player) ? "lineup" : "draft";
      gameState.notice = "Jogador escalado. Novo sorteio liberado.";
      refreshStats(gameState);
      return true;
    }
    if (type === ACTIONS.SELECT_FIELD_CARD) {
      if (!["draft", "lineup"].includes(gameState.phase) || !gameState.lineup[action.index]?.player) return false;
      gameState.selectedSlot = action.index;
      gameState.notice = "Escolha uma vaga iluminada para mover ou trocar.";
      return true;
    }
    if (type === ACTIONS.CANCEL_MOVE) {
      gameState.selectedSlot = null;
      gameState.notice = "Movimento cancelado.";
      return true;
    }
    if (type === ACTIONS.MOVE_PLAYER || type === ACTIONS.SWAP_PLAYERS) {
      const sourceIndex = action.sourceIndex ?? gameState.selectedSlot;
      const targetIndex = action.targetIndex;
      if (!["draft", "lineup"].includes(gameState.phase) || !canMoveTo(gameState, sourceIndex, targetIndex)) {
        gameState.notice = "Posição incompatível.";
        return false;
      }
      const source = gameState.lineup[sourceIndex];
      const target = gameState.lineup[targetIndex];
      const wasSwap = Boolean(target.player);
      [source.player, target.player] = [target.player, source.player];
      gameState.selectedSlot = null;
      gameState.notice = wasSwap ? "Jogadores trocados." : "Jogador movido.";
      refreshStats(gameState);
      return true;
    }
    if (type === ACTIONS.START_CAMPAIGN) {
      if (gameState.phase !== "lineup" || gameState.lineup.some((slot) => !slot.player)) return false;
      const plan = action.campaign || simulateCampaign(gameState.lineup, gameState.tactic, action.options || { runSeed: gameState.runSeed });
      gameState.phase = "campaign";
      gameState.selectedSlot = null;
      gameState.campaign = { ...plan, visibleMatches: [], revealed: 0 };
      gameState.result = null;
      gameState.notice = "A campanha começou. O time agora está travado.";
      return true;
    }
    if (type === ACTIONS.SIMULATE_NEXT_MATCH) {
      if (gameState.phase !== "campaign" || !gameState.campaign || gameState.campaign.revealed >= gameState.campaign.matches.length) return false;
      gameState.campaign.visibleMatches.push(gameState.campaign.matches[gameState.campaign.revealed]);
      gameState.campaign.revealed += 1;
      return true;
    }
    if (type === ACTIONS.FINISH_CAMPAIGN) {
      if (gameState.phase !== "campaign" || !gameState.campaign || gameState.campaign.revealed < gameState.campaign.matches.length) return false;
      gameState.phase = "result";
      gameState.result = gameState.campaign.result;
      gameState.finishedRun = buildFinishedRun(gameState);
      gameState.selectedReportRun = null;
      gameState.activeResultTab = "result";
      gameState.notice = gameState.result.title;
      return true;
    }
    return false;
  }

  function dispatch(action, targetState = state) {
    const changed = applyAction(targetState, action);
    if (changed && typeof document !== "undefined" && targetState === state) renderGame();
    return changed;
  }

  function rarityForRating(rating) {
    const value = Number(rating || 0);
    if (value >= 95) return "legendary";
    if (value >= 90) return "elite";
    if (value >= 85) return "star";
    if (value >= 80) return "solid";
    return "common";
  }

  function initials(name) {
    return String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
  }

  function achievementDefinitions(gameState) {
    const progress = gameState.progress;
    return [
      ["first_draft", "Primeiro Draft", progress.runs >= 1],
      ["qualified", "Classificado", Boolean(gameState.campaign?.qualified)],
      ["champion", "Campeão", gameState.result?.code === "champion"],
      ["seven_zero", "Achou o 7 × 0", Boolean(gameState.campaign?.sevenZero)],
      ["team_90", "Time 90+", gameState.stats.overall >= 90],
      ["chem_80", "Química 80+", gameState.stats.chemistry >= 80],
      ["group_miracle", "Milagre do Grupo", gameState.campaign?.groupTable?.points === 3 && gameState.campaign?.qualified],
    ];
  }

  function loadProgress() {
    if (typeof localStorage === "undefined") return emptyProgress();
    try { return { ...emptyProgress(), ...JSON.parse(localStorage.getItem(PROGRESS_KEY) || "{}") }; }
    catch (_error) { return emptyProgress(); }
  }

  function saveProgress() {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(state.progress));
  }

  function loadRunHistory() {
    if (typeof localStorage === "undefined") return [];
    try {
      const history = JSON.parse(localStorage.getItem(RUN_HISTORY_KEY) || "[]");
      return Array.isArray(history) ? history.slice(0, 10) : [];
    } catch (_error) {
      return [];
    }
  }

  function saveFinishedRun(run) {
    state.runHistory = mergeRunHistory(state.runHistory, run);
    if (typeof localStorage !== "undefined") localStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(state.runHistory));
  }

  function updateProgress() {
    const progress = state.progress;
    progress.runs += 1;
    progress.highestOverall = Math.max(progress.highestOverall, state.stats.overall);
    progress.highestChemistry = Math.max(progress.highestChemistry, state.stats.chemistry);
    progress.highestFit = Math.max(progress.highestFit, state.stats.fit);
    progress.sevenZeroFound ||= Boolean(state.campaign?.sevenZero);
    if (state.result?.code === "champion") progress.titles += 1;
    const rank = { Nenhuma: 0, "Fase de grupos": 1, Oitavas: 2, Quartas: 3, Semifinal: 4, Final: 5, Campeão: 6 };
    const campaignName = state.result?.code === "champion" ? "Campeão" : state.result?.code === "runner_up" ? "Final" : state.result?.code === "group" ? "Fase de grupos" : state.result?.title?.replace("Caiu em ", "").replace(".", "") || "Nenhuma";
    if ((rank[campaignName] || 0) > (rank[progress.bestCampaign] || 0)) progress.bestCampaign = campaignName;
    achievementDefinitions(state).forEach(([id, _label, unlocked]) => { if (unlocked && !progress.achievements.includes(id)) progress.achievements.push(id); });
    state.achievements = [...progress.achievements];
    saveProgress();
  }

  const gameApi = {
    ACTIONS,
    state,
    createGameState,
    dispatch,
    applyAction,
    compatibleSlotsForPlayer,
    preferredSlotsForPlayer,
    slotCompatibilityScore,
    positionMetrics,
    calculateTeamPower,
    calculateOpponentPower,
    calculateMatchOdds,
    simulateScore,
    simulateMatch,
    simulateGroupStage,
    calculateGroupTable,
    determineGroupQualification,
    simulateKnockout,
    simulateCampaign,
    matchOutcome,
    buildFinishedRun,
    mergeRunHistory,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = gameApi;
  if (typeof document === "undefined") return;
  window.DreamCupGame = gameApi;

  const el = (id) => document.getElementById(id);
  const dom = Object.fromEntries([
    "rollBtn", "skipBtn", "playerList", "drawCard", "rollTitle", "pickedStat", "overallStat", "chemStat", "fitStat",
    "skipCount", "simulateBtn", "resetBtn", "resultResetBtn", "matchTimeline", "playerSearch", "dbSource", "optionsToggle",
    "optionsPanel", "draftStatus", "lineupStatus", "lineup", "draftLockBadge", "cancelMoveBtn", "campaignPhase", "campaignTitle",
    "groupPoints", "groupBalance", "groupGames", "simulateHint", "resultScreen", "resultTitle", "resultReason", "resultStats",
    "resultAchievements", "resultLineup", "resultMatches", "resultStatistics", "runHistory", "progressRuns", "achievementList",
  ].map((id) => [id, el(id)]));

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status} em ${url}`);
    return response.json();
  }

  async function loadDatabase() {
    try { return await fetchJson("/static/data/dream_cup_database.json"); }
    catch (_error) { return fetchJson("/static/data/dream_cup_seed.json"); }
  }

  function displayName(player) {
    return state.mode === "memory" ? `${player.role} ${player.shirt_number ? `#${player.shirt_number}` : "?"}` : String(player.name || "Jogador").trim();
  }

  function renderHud() {
    refreshStats(state);
    const picked = state.lineup.filter((slot) => slot.player).length;
    dom.pickedStat.textContent = `${picked}/11`;
    dom.overallStat.textContent = state.stats.overall || "--";
    dom.chemStat.textContent = state.stats.chemistry || "--";
    dom.fitStat.textContent = state.stats.fit ? `${state.stats.fit}%` : "--";
    dom.skipCount.textContent = state.skipsLeft;
    dom.draftLockBadge.textContent = state.draftLocked ? "Escolha obrigatória" : "Livre";
    dom.draftLockBadge.classList.toggle("locked", state.draftLocked);
  }

  function renderDraft() {
    dom.rollBtn.disabled = state.draftLocked || !["draft", "lineup"].includes(state.phase);
    dom.skipBtn.disabled = !state.draftLocked || state.skipsLeft <= 0 || state.phase === "campaign" || state.phase === "result";
    dom.draftStatus.textContent = state.notice;
    if (!state.currentSquad) {
      dom.rollTitle.textContent = "Seu próximo elenco";
      dom.drawCard.className = "draw-card empty";
      dom.drawCard.innerHTML = "<p>Role para revelar um elenco histórico.</p>";
      dom.playerList.innerHTML = '<p class="empty-copy">As figurinhas aparecem depois do sorteio.</p>';
      return;
    }
    dom.rollTitle.textContent = `${state.currentSquad.nation} ${state.currentSquad.year}`;
    dom.drawCard.className = "draw-card dealt";
    dom.drawCard.innerHTML = `<span class="squad-orb">${initials(state.currentSquad.nation)}</span><div><p class="eyebrow">${escapeHtml(state.currentSquad.tournament || "Copa do Mundo")}</p><h3>${escapeHtml(state.currentSquad.nation)} ${state.currentSquad.year}</h3><p>${escapeHtml(state.currentSquad.aura || "elenco histórico")} · força ${state.currentSquad.strength || "--"}</p></div>`;
    const picked = chosenPlayerKeys(state);
    const term = normalizeText(state.filter);
    const players = state.currentSquad.players
      .filter((player) => !term || normalizeText(`${player.name} ${player.role} ${player.position_name || ""} ${player.shirt_number || ""}`).includes(term))
      .slice().sort((a, b) => Number(b.rating || 0) - Number(a.rating || 0));
    dom.playerList.innerHTML = "";
    players.forEach((player) => {
      const disabled = !availableSlotsFor(state, player).length || picked.has(playerKey(player));
      const rarity = rarityForRating(player.rating);
      const button = document.createElement("button");
      button.className = `player-card rarity-${rarity} ${disabled ? "incompatible" : ""}`;
      button.type = "button";
      button.disabled = disabled;
      button.innerHTML = `<span class="player-avatar"><b>${escapeHtml(initials(player.name))}</b><small>${POSITION_ICONS[player.role] || "◆"}</small></span><span class="player-copy"><span class="player-name">${escapeHtml(displayName(player))}</span><span class="player-meta">${escapeHtml(player.nation)} ${player.year} · ${escapeHtml(player.trait_label || roleLabel(player.role))}</span><span class="player-position">${escapeHtml(player.role_label || roleLabel(player.role))} · #${player.shirt_number || "—"}</span></span><span class="overall-badge"><strong>${state.mode === "memory" ? "?" : player.rating || "--"}</strong><small>${rarity}</small></span>`;
      button.addEventListener("click", () => dispatch({ type: ACTIONS.PICK_PLAYER, player }));
      dom.playerList.appendChild(button);
    });
  }

  function renderLineup() {
    dom.lineup.innerHTML = "";
    const rows = Array.from({ length: FORMATIONS[state.formation].length }, (_, row) => state.lineup.filter((slot) => slot.row === row));
    rows.forEach((slots) => {
      const rowNode = document.createElement("div");
      rowNode.className = "pitch-row";
      slots.forEach((slot) => {
        const index = state.lineup.indexOf(slot);
        const score = slot.player ? slotCompatibilityScore(slot.player, slot.pos) : 0;
        const selected = state.selectedSlot === index;
        const compatible = state.selectedSlot !== null && canMoveTo(state, state.selectedSlot, index);
        const rarity = slot.player ? rarityForRating(slot.player.rating) : "empty";
        const button = document.createElement("button");
        button.type = "button";
        button.className = `slot ${slot.player ? "filled" : ""} rarity-${rarity} ${selected ? "selected" : ""} ${compatible ? "compatible-slot" : ""}`;
        button.innerHTML = slot.player
          ? `<span class="field-avatar">${escapeHtml(initials(slot.player.name))}</span><span class="slot-pos">${slot.pos}</span><span class="slot-name">${escapeHtml(displayName(slot.player))}</span><span class="slot-meta">${score === 1 ? "Natural" : score === 0.8 ? "Secundária" : "Improvisado"}</span><span class="rating-badge">${state.mode === "memory" ? "?" : slot.player.rating}</span>`
          : `<span class="slot-pos">${slot.pos}</span><span class="slot-name">Vaga</span><span class="slot-meta">${roleLabel(roleBySlot(slot.pos))}</span>`;
        button.addEventListener("click", () => {
          if (state.selectedSlot === null) dispatch({ type: ACTIONS.SELECT_FIELD_CARD, index });
          else if (state.selectedSlot === index) dispatch({ type: ACTIONS.CANCEL_MOVE });
          else dispatch({ type: slot.player ? ACTIONS.SWAP_PLAYERS : ACTIONS.MOVE_PLAYER, targetIndex: index });
        });
        rowNode.appendChild(button);
      });
      dom.lineup.appendChild(rowNode);
    });
    dom.cancelMoveBtn.classList.toggle("hidden", state.selectedSlot === null);
    dom.lineupStatus.textContent = state.selectedSlot === null ? "Clique em uma figurinha para reorganizar o time." : state.notice;
  }

  function matchClass(match) {
    return matchOutcome(match);
  }

  function renderCampaign() {
    const visibleGroupMatches = (state.campaign?.visibleMatches || []).filter((match) => GROUP_STAGES.includes(match.stage));
    const table = visibleGroupMatches.length ? calculateGroupTable(visibleGroupMatches) : { points: 0, balance: 0, played: 0 };
    dom.groupPoints.textContent = table.points;
    dom.groupBalance.textContent = table.balance > 0 ? `+${table.balance}` : table.balance;
    dom.groupGames.textContent = `${Math.min(table.played, 3)}/3`;
    dom.campaignPhase.textContent = state.phase === "campaign" ? "Em jogo" : state.phase === "result" ? "Encerrada" : "Draft";
    dom.campaignTitle.textContent = state.campaign?.revealed > 3 ? "Mata-mata" : "Rumo à final";
    const complete = state.lineup.every((slot) => slot.player);
    dom.simulateBtn.disabled = !complete || state.phase === "campaign" || state.phase === "result";
    dom.simulateBtn.classList.toggle("hidden", state.phase === "campaign" || state.phase === "result");
    dom.simulateBtn.textContent = state.phase === "campaign" ? "Simulando..." : complete ? "Começar campanha" : `Faltam ${state.lineup.filter((slot) => !slot.player).length}`;
    dom.simulateHint.textContent = state.phase === "campaign"
      ? "Campanha em andamento. O draft está bloqueado."
      : state.phase === "result"
        ? "Run encerrada. Abra a ficha completa acima."
        : complete ? "Time fechado. A Copa vai testar força, química e encaixe." : "Complete o onze para começar a campanha.";
    const matches = state.campaign?.visibleMatches || [];
    dom.matchTimeline.innerHTML = matches.length ? "" : '<p class="empty-copy">Os placares aparecerão aqui.</p>';
    matches.forEach((match) => {
      const node = document.createElement("div");
      node.className = `match-row ${matchClass(match)}`;
      node.innerHTML = `<span class="match-stage">${escapeHtml(match.stage)}</span><strong>${escapeHtml(match.opponent)}</strong><span class="match-score">${match.goalsFor} × ${match.goalsAgainst}</span>`;
      dom.matchTimeline.appendChild(node);
    });
  }

  function renderProgress() {
    dom.progressRuns.textContent = `${state.progress.runs} run${state.progress.runs === 1 ? "" : "s"}`;
    const definitions = achievementDefinitions(state);
    dom.achievementList.innerHTML = definitions.slice(0, 5).map(([id, label]) => `<span class="${state.progress.achievements.includes(id) ? "unlocked" : ""}" title="${escapeHtml(label)}">${state.progress.achievements.includes(id) ? "★" : "☆"}</span>`).join("");
  }

  function fitLabel(score) {
    return score === 1 ? "Natural" : score === 0.8 ? "Secundário" : "Improvisado";
  }

  function resultLabel(run) {
    return run?.result?.title || run?.result?.code || "Run encerrada";
  }

  function renderResultTabs() {
    document.querySelectorAll("[data-result-tab]").forEach((button) => button.classList.toggle("active", button.dataset.resultTab === state.activeResultTab));
    document.querySelectorAll("[data-result-panel]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.resultPanel !== state.activeResultTab));
  }

  function renderRunDetails(run) {
    if (!run) return;
    dom.resultTitle.textContent = resultLabel(run);
    dom.resultReason.textContent = run.reason || "A campanha terminou.";
    dom.resultStats.innerHTML = `<span><small>OVR</small><strong>${run.stats.overall}</strong></span><span><small>Química</small><strong>${run.stats.chemistry}</strong></span><span><small>Encaixe</small><strong>${run.stats.fit}%</strong></span><span><small>Pontos</small><strong>${run.stats.points}</strong></span>`;
    dom.resultLineup.innerHTML = run.lineup.map((player) => `<article class="run-player-row"><span class="run-slot">${escapeHtml(player.slot)}</span><span class="run-player-copy"><strong>${escapeHtml(player.name)}</strong><small>${escapeHtml(player.nation || "Seleção")} ${escapeHtml(player.year || "")} · ${escapeHtml(player.role_label)}</small></span><span class="run-fit">${fitLabel(player.fitScore)}</span><b>${player.rating || "--"}</b></article>`).join("");
    dom.resultMatches.innerHTML = run.matches.map((match) => `<article class="run-match-row ${escapeHtml(match.outcome)}"><span><small>${escapeHtml(match.stage)}</small><strong>${escapeHtml(match.opponent)}</strong></span><b>${match.goalsFor} × ${match.goalsAgainst}</b><span class="power-pair"><small>Seu poder ${match.teamPower}</small><small>Rival ${match.opponentPower}</small></span>${match.sevenZero ? '<em class="seven-zero-badge">7 × 0</em>' : ""}</article>`).join("");
    dom.resultStatistics.innerHTML = `
      <div class="result-stats expanded">
        <span><small>Gols pró</small><strong>${run.stats.goalsFor}</strong></span>
        <span><small>Gols contra</small><strong>${run.stats.goalsAgainst}</strong></span>
        <span><small>Saldo</small><strong>${run.stats.balance > 0 ? "+" : ""}${run.stats.balance}</strong></span>
        <span><small>7 × 0</small><strong>${run.sevenZero ? "Encontrado" : "Não"}</strong></span>
      </div>
      <p class="run-reason"><strong>Motivo:</strong> ${escapeHtml(run.reason || "Campanha concluída.")}</p>`;
  }

  function renderRunHistory() {
    dom.runHistory.innerHTML = state.runHistory.length ? state.runHistory.map((run) => {
      const date = new Date(run.createdAt);
      const label = Number.isNaN(date.getTime()) ? "Data indisponível" : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
      return `<article class="run-history-row"><span><small>${escapeHtml(label)}</small><strong>${escapeHtml(resultLabel(run))}</strong><em>OVR ${run.stats.overall} · QUI ${run.stats.chemistry} · Encaixe ${run.stats.fit}%</em></span><button type="button" data-run-details="${escapeHtml(run.id)}">Ver detalhes</button></article>`;
    }).join("") : '<p class="empty-copy">Esta é sua primeira ficha de campanha.</p>';
  }

  function renderResult() {
    const visible = state.phase === "result";
    dom.resultScreen.classList.toggle("hidden", !visible);
    if (!visible) return;
    const run = state.selectedReportRun || state.finishedRun;
    renderRunDetails(run);
    renderRunHistory();
    renderResultTabs();
    const unlocked = achievementDefinitions(state).filter(([id]) => state.progress.achievements.includes(id));
    dom.resultAchievements.innerHTML = unlocked.map(([_id, label]) => `<span>★ ${escapeHtml(label)}</span>`).join("");
  }

  function renderGame() {
    document.body.className = `platform-theme dream-cup-page phase-${state.phase}`;
    renderHud();
    renderDraft();
    renderLineup();
    renderCampaign();
    renderProgress();
    renderResult();
  }

  function revealCampaign() {
    const delay = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 40 : 720;
    const reveal = () => {
      if (state.phase !== "campaign") return;
      if (state.campaign.revealed < state.campaign.matches.length) {
        dispatch({ type: ACTIONS.SIMULATE_NEXT_MATCH });
        window.setTimeout(reveal, delay);
      } else {
        dispatch({ type: ACTIONS.FINISH_CAMPAIGN });
        saveFinishedRun(state.finishedRun);
        updateProgress();
        renderGame();
      }
    };
    window.setTimeout(reveal, delay);
  }

  function bindControls() {
    dom.optionsToggle.addEventListener("click", () => {
      const opening = dom.optionsPanel.classList.contains("hidden");
      dom.optionsPanel.classList.toggle("hidden", !opening);
      dom.optionsToggle.setAttribute("aria-expanded", String(opening));
    });
    document.querySelectorAll("[data-formation]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-formation]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.formation = button.dataset.formation;
      dispatch({ type: ACTIONS.RESET_RUN, formation: state.formation });
    }));
    document.querySelectorAll("[data-mode]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.mode = button.dataset.mode;
      renderGame();
    }));
    document.querySelectorAll("[data-tactic]").forEach((button) => button.addEventListener("click", () => {
      document.querySelectorAll("[data-tactic]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      state.tactic = button.dataset.tactic;
      renderGame();
    }));
    dom.rollBtn.addEventListener("click", () => dispatch({ type: ACTIONS.ROLL_SQUAD }));
    dom.skipBtn.addEventListener("click", () => dispatch({ type: ACTIONS.SKIP_SQUAD }));
    dom.cancelMoveBtn.addEventListener("click", () => dispatch({ type: ACTIONS.CANCEL_MOVE }));
    dom.resetBtn.addEventListener("click", () => dispatch({ type: ACTIONS.RESET_RUN }));
    dom.resultResetBtn.addEventListener("click", () => dispatch({ type: ACTIONS.RESET_RUN }));
    document.querySelectorAll("[data-result-tab]").forEach((button) => button.addEventListener("click", () => {
      state.activeResultTab = button.dataset.resultTab;
      renderResultTabs();
    }));
    dom.runHistory.addEventListener("click", (event) => {
      const button = event.target.closest("[data-run-details]");
      if (!button) return;
      state.selectedReportRun = state.runHistory.find((run) => run.id === button.dataset.runDetails) || null;
      state.activeResultTab = "result";
      renderResult();
    });
    dom.simulateBtn.addEventListener("click", () => {
      if (dispatch({ type: ACTIONS.START_CAMPAIGN })) revealCampaign();
    });
    dom.playerSearch.addEventListener("input", () => { state.filter = dom.playerSearch.value || ""; renderDraft(); });
  }

  async function init() {
    bindControls();
    state.progress = loadProgress();
    state.runHistory = loadRunHistory();
    try {
      const database = await loadDatabase();
      dispatch({ type: ACTIONS.BOOT_GAME, database });
      dom.dbSource.textContent = database.source || "Banco local da Copa dos Sonhos";
    } catch (error) {
      state.phase = "draft";
      state.notice = `Não consegui carregar o banco do jogo: ${error.message}`;
      renderGame();
    }
  }

  init();
})();
