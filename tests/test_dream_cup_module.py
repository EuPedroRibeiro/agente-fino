from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class DreamCupModuleTests(TestCase):
    def run_game_js(self, expression: str):
        if not shutil.which("node"):
            self.skipTest("Node.js não está disponível para validar a lógica do jogo.")
        script = f"const game=require('./app/static/js/dream_cup.js'); console.log(JSON.stringify({expression}));"
        completed = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(completed.stdout)

    def game_files(self):
        return {
            "html": (ROOT / "app" / "templates" / "dream_cup.html").read_text(encoding="utf-8"),
            "css": (ROOT / "app" / "static" / "css" / "dream_cup.css").read_text(encoding="utf-8"),
            "js": (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8"),
        }

    def test_dream_cup_routes_and_agent_entry_are_registered(self):
        route_file = (ROOT / "app" / "routes" / "dream_cup.py").read_text(encoding="utf-8")
        agent_html = (ROOT / "app" / "templates" / "agent.html").read_text(encoding="utf-8")
        self.assertIn("/agent/copa-dos-sonhos", route_file)
        self.assertIn("/agent/dream-cup", route_file)
        self.assertIn("dream_cup.html", route_file)
        self.assertIn("/agent/copa-dos-sonhos", agent_html)

    def test_real_database_and_seed_are_preserved(self):
        for file_name in ("dream_cup_database.json", "dream_cup_seed.json"):
            path = ROOT / "app" / "static" / "data" / file_name
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("squads", data)
            self.assertGreaterEqual(len(data["squads"]), 10)
            self.assertGreaterEqual(len(data["squads"][0]["players"]), 10)
        generated = json.loads((ROOT / "app" / "static" / "data" / "dream_cup_database.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(generated["stats"].get("squads", 0), 100)
        self.assertGreaterEqual(generated["stats"].get("players") or generated["stats"].get("unique_players", 0), 1000)

    def test_state_machine_and_required_actions_exist(self):
        files = self.game_files()
        for required in (
            "createGameState",
            "dispatch",
            "simulateCampaign",
            "simulateGroupStage",
            "calculateGroupTable",
            "determineGroupQualification",
            "simulateKnockout",
            "calculateTeamPower",
            "calculateOpponentPower",
            "calculateMatchOdds",
            "simulateScore",
            "compatibleSlotsForPlayer",
        ):
            self.assertIn(required, files["js"])
        result = self.run_game_js("""(() => {
          const state=game.createGameState();
          return {phase:state.phase,skipsLeft:state.skipsLeft,lineup:state.lineup.length,actions:Object.keys(game.ACTIONS)};
        })()""")
        self.assertEqual(result["phase"], "boot")
        self.assertEqual(result["skipsLeft"], 3)
        self.assertEqual(result["lineup"], 11)
        for action in (
            "BOOT_GAME", "START_RUN", "ROLL_SQUAD", "SKIP_SQUAD", "PICK_PLAYER", "SELECT_FIELD_CARD",
            "MOVE_PLAYER", "SWAP_PLAYERS", "CANCEL_MOVE", "START_CAMPAIGN", "SIMULATE_NEXT_MATCH",
            "FINISH_CAMPAIGN", "RESET_RUN",
        ):
            self.assertIn(action, result["actions"])

    def test_draft_lock_blocks_second_roll_and_skip_spends_wildcard(self):
        result = self.run_game_js("""(() => {
          const s=game.createGameState({phase:'draft'});
          const squad={id:'br-02',nation:'Brasil',year:2002,players:[{name:'Goleiro',role:'GK',rating:85}]};
          const first=game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},s);
          const second=game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},s);
          const skip=game.dispatch({type:game.ACTIONS.SKIP_SQUAD},s);
          return {first,second,skip,draftLocked:s.draftLocked,skipsLeft:s.skipsLeft,currentSquad:s.currentSquad};
        })()""")
        self.assertTrue(result["first"])
        self.assertFalse(result["second"])
        self.assertTrue(result["skip"])
        self.assertFalse(result["draftLocked"])
        self.assertEqual(result["skipsLeft"], 2)
        self.assertIsNone(result["currentSquad"])

    def test_pick_player_unlocks_roll_and_incompatible_squad_is_free(self):
        result = self.run_game_js("""(() => {
          const player={name:'Goleiro',role:'GK',rating:85};
          const squad={id:'br-02',nation:'Brasil',year:2002,players:[player]};
          const pickedState=game.createGameState({phase:'draft'});
          game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},pickedState);
          const picked=game.dispatch({type:game.ACTIONS.PICK_PLAYER,player},pickedState);
          const noFitState=game.createGameState({phase:'draft'});
          noFitState.lineup[10].player={name:'Outro goleiro',role:'GK',rating:80};
          const noFit=game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},noFitState);
          return {
            picked,pickUnlocked:!pickedState.draftLocked,pickCurrent:pickedState.currentSquad,
            noFit,noFitUnlocked:!noFitState.draftLocked,noFitNotice:noFitState.notice
          };
        })()""")
        self.assertTrue(result["picked"])
        self.assertTrue(result["pickUnlocked"])
        self.assertIsNone(result["pickCurrent"])
        self.assertTrue(result["noFit"])
        self.assertTrue(result["noFitUnlocked"])
        self.assertIn("novo sorteio liberado", result["noFitNotice"])

    def test_position_compatibility_and_bad_fit_penalty(self):
        result = self.run_game_js("""(() => {
          const make=(role,rating=90)=>({name:'Jogador '+role,role,rating,nation:'Brasil',year:2002});
          const good=[
            {pos:'GK',player:make('GK')},{pos:'CB',player:make('DF')},{pos:'CB',player:make('DF')},
            {pos:'LB',player:make('DF')},{pos:'RB',player:make('DF')},{pos:'CM',player:make('MF')},
            {pos:'CM',player:make('MF')},{pos:'AM',player:make('MF')},{pos:'LW',player:make('FW')},
            {pos:'ST',player:make('FW')},{pos:'RW',player:make('FW')}
          ];
          const bad=good.map((slot,index)=>({...slot,pos:index===0?'ST':index<5?'CM':'CB'}));
          return {
            goalkeeper:game.compatibleSlotsForPlayer({name:'Teste',role:'GK'}),
            roberto:game.compatibleSlotsForPlayer({name:'Roberto Carlos',role:'DF'}),
            goodFit:game.positionMetrics(good).fitPercent,badFit:game.positionMetrics(bad).fitPercent,
            goodPower:game.calculateTeamPower(good),badPower:game.calculateTeamPower(bad)
          };
        })()""")
        self.assertEqual(result["goalkeeper"], ["GK"])
        self.assertEqual(result["roberto"], ["LB", "LM"])
        self.assertGreater(result["goodFit"], result["badFit"])
        self.assertGreater(result["goodPower"], result["badPower"])

    def test_three_group_losses_end_in_group_stage(self):
        result = self.run_game_js("""(() => {
          const make=(role)=>({name:'J '+role,role,rating:88,nation:'Brasil',year:2002});
          const lineup=[
            {pos:'GK',player:make('GK')},{pos:'CB',player:make('DF')},{pos:'CB',player:make('DF')},
            {pos:'LB',player:make('DF')},{pos:'RB',player:make('DF')},{pos:'CM',player:make('MF')},
            {pos:'CM',player:make('MF')},{pos:'AM',player:make('MF')},{pos:'LW',player:make('FW')},
            {pos:'ST',player:make('FW')},{pos:'RW',player:make('FW')}
          ];
          return game.simulateCampaign(lineup,'balanced',{group:{randomValues:[0,0,0],opponentPowers:[100,100,100],qualificationRandom:0}});
        })()""")
        self.assertFalse(result["qualified"])
        self.assertEqual(result["groupTable"]["losses"], 3)
        self.assertEqual(result["result"]["code"], "group")
        self.assertEqual(result["result"]["title"], "Caiu na fase de grupos.")
        self.assertEqual(len(result["matches"]), 3)

    def test_losing_round_of_16_stops_campaign_at_correct_stage(self):
        result = self.run_game_js("""(() => {
          const make=(role)=>({name:'J '+role,role,rating:90,nation:'Brasil',year:2002});
          const lineup=[
            {pos:'GK',player:make('GK')},{pos:'CB',player:make('DF')},{pos:'CB',player:make('DF')},
            {pos:'LB',player:make('DF')},{pos:'RB',player:make('DF')},{pos:'CM',player:make('MF')},
            {pos:'CM',player:make('MF')},{pos:'AM',player:make('MF')},{pos:'LW',player:make('FW')},
            {pos:'ST',player:make('FW')},{pos:'RW',player:make('FW')}
          ];
          return game.simulateCampaign(lineup,'balanced',{
            group:{randomValues:[.99,.99,.99],opponentPowers:[60,60,60],qualificationRandom:.9},
            knockout:{randomValues:[0],opponentPowers:[100]}
          });
        })()""")
        self.assertTrue(result["qualified"])
        self.assertEqual(result["result"]["code"], "oitavas")
        self.assertEqual(result["result"]["title"], "Caiu em Oitavas.")
        self.assertEqual(len(result["matches"]), 4)

    def test_seven_zero_requires_strong_well_fitted_team(self):
        result = self.run_game_js("""(() => {
          const make=(role,rating)=>({name:'J '+role,role,rating,nation:'Brasil',year:2002});
          const build=(rating)=>[
            {pos:'GK',player:make('GK',rating)},{pos:'CB',player:make('DF',rating)},{pos:'CB',player:make('DF',rating)},
            {pos:'LB',player:make('DF',rating)},{pos:'RB',player:make('DF',rating)},{pos:'CM',player:make('MF',rating)},
            {pos:'CM',player:make('MF',rating)},{pos:'AM',player:make('MF',rating)},{pos:'LW',player:make('FW',rating)},
            {pos:'ST',player:make('FW',rating)},{pos:'RW',player:make('FW',rating)}
          ];
          return {
            strong:game.simulateScore(build(96),'balanced',60,0,.999,false),
            weak:game.simulateScore(build(72),'balanced',60,0,.999,false)
          };
        })()""")
        self.assertTrue(result["strong"]["sevenZero"])
        self.assertEqual(result["strong"]["goalsFor"], 7)
        self.assertFalse(result["weak"]["sevenZero"])

    def test_finished_run_saves_full_lineup_matches_and_stats(self):
        result = self.run_game_js("""(() => {
          const make=(role,index)=>({
            name:'Jogador '+index,role,rating:88+index%4,nation:'Brasil',year:2002,
            role_label:'Função '+role,shirt_number:index+1,trait_label:'Traço '+index
          });
          const lineup=[
            {pos:'GK',player:make('GK',0)},{pos:'CB',player:make('DF',1)},{pos:'CB',player:make('DF',2)},
            {pos:'LB',player:make('DF',3)},{pos:'RB',player:make('DF',4)},{pos:'CM',player:make('MF',5)},
            {pos:'CM',player:make('MF',6)},{pos:'AM',player:make('MF',7)},{pos:'LW',player:make('FW',8)},
            {pos:'ST',player:make('FW',9)},{pos:'RW',player:make('FW',10)}
          ];
          const plan=game.simulateCampaign(lineup,'balanced',{
            group:{randomValues:[.99,.99,.99],opponentPowers:[60,61,62]},
            knockout:{randomValues:[.99,.99,.99,.99],opponentPowers:[70,72,74,76]}
          });
          const state=game.createGameState({
            phase:'campaign',lineup,campaign:{...plan,visibleMatches:[...plan.matches],revealed:plan.matches.length},
            stats:{overall:90,chemistry:82,fit:96}
          });
          const finished=game.dispatch({type:game.ACTIONS.FINISH_CAMPAIGN},state);
          return {finished,phase:state.phase,run:state.finishedRun};
        })()""")
        self.assertTrue(result["finished"])
        self.assertEqual(result["phase"], "result")
        run = result["run"]
        self.assertEqual(len(run["lineup"]), 11)
        self.assertGreaterEqual(len(run["matches"]), 4)
        for key in ("id", "createdAt", "result", "stats", "lineup", "matches", "sevenZero", "reason"):
            self.assertIn(key, run)
        for key in ("slot", "name", "nation", "year", "rating", "role_label", "shirt_number", "trait_label", "fitScore"):
            self.assertIn(key, run["lineup"][0])
        for match in run["matches"]:
            for key in ("stage", "opponent", "opponentPower", "teamPower", "goalsFor", "goalsAgainst", "outcome"):
                self.assertIn(key, match)

    def test_run_history_is_limited_to_ten_and_uses_expected_storage_key(self):
        files = self.game_files()
        self.assertIn("dream_cup_run_history_v1", files["js"])
        result = self.run_game_js("""(() => {
          let history=[];
          for(let index=0;index<12;index+=1) history=game.mergeRunHistory(history,{id:'run-'+index});
          return {length:history.length,first:history[0].id,last:history[history.length-1].id};
        })()""")
        self.assertEqual(result["length"], 10)
        self.assertEqual(result["first"], "run-11")
        self.assertEqual(result["last"], "run-2")

    def test_campaign_and_result_phases_block_draft_actions(self):
        result = self.run_game_js("""(() => {
          const squad={id:'br-02',nation:'Brasil',year:2002,players:[{name:'Goleiro',role:'GK',rating:85}]};
          const campaign=game.createGameState({phase:'campaign'});
          const finished=game.createGameState({phase:'result'});
          return {
            campaignRoll:game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},campaign),
            resultRoll:game.dispatch({type:game.ACTIONS.ROLL_SQUAD,squad},finished),
            campaignPick:game.dispatch({type:game.ACTIONS.PICK_PLAYER,player:squad.players[0]},campaign),
            resultPick:game.dispatch({type:game.ACTIONS.PICK_PLAYER,player:squad.players[0]},finished)
          };
        })()""")
        self.assertFalse(result["campaignRoll"])
        self.assertFalse(result["resultRoll"])
        self.assertFalse(result["campaignPick"])
        self.assertFalse(result["resultPick"])

    def test_ui_is_a_game_screen_with_hud_deck_field_campaign_and_result(self):
        files = self.game_files()
        for marker in ("game-hud", "draft-board", "field-board", "campaign-board", "resultScreen", "progress-panel"):
            self.assertIn(marker, files["html"])
        for marker in ("Minha escalação", "Jogos da campanha", "Estatísticas da run", "Histórico recente", "resultLineup", "resultMatches", "runHistory"):
            self.assertIn(marker, files["html"])
        for marker in (".player-avatar", ".rarity-legendary", ".slot.selected", ".slot.compatible-slot", ".phase-campaign .draft-board", ".result-screen"):
            self.assertIn(marker, files["css"])
        self.assertIn(".phase-campaign #simulateBtn", files["css"])
        self.assertIn(".phase-result .draft-board", files["css"])
        self.assertIn("Nova run", files["html"])
        self.assertIn("overflow:hidden", files["css"])
        self.assertIn("text-overflow:ellipsis", files["css"])
        self.assertIn("white-space:nowrap", files["css"])
        self.assertIn("min-width:0", files["css"])
        self.assertIn("user-select:none", files["css"])
        self.assertIn("cursor:pointer", files["css"])
        self.assertNotIn("quiz", "\n".join(files.values()).lower())

    def test_progression_uses_local_storage_not_postgres(self):
        files = self.game_files()
        self.assertIn("localStorage", files["js"])
        self.assertIn("dream_cup_progress_v1", files["js"])
        self.assertIn("Primeiro Draft", files["js"])
        self.assertIn("Achou o 7 × 0", files["js"])
        self.assertNotIn("postgres", files["js"].lower())

    def test_no_external_or_official_assets_and_no_autoplay(self):
        files = self.game_files()
        combined = "\n".join(files.values()).lower()
        for forbidden in ("http://", "https://", "cdn", "autoplay", "<audio", "<canvas", "nintendo", "mario"):
            self.assertNotIn(forbidden, combined)

    def test_builder_keeps_source_attribution_and_license(self):
        builder = (ROOT / "scripts" / "build_dream_cup_database.py").read_text(encoding="utf-8")
        self.assertIn("Fjelstul World Cup Database", builder)
        self.assertIn("CC-BY-SA-4.0", builder)
        self.assertIn("squads.csv", builder)
