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

    def test_dream_cup_routes_are_registered(self):
        route_file = (ROOT / "app" / "routes" / "dream_cup.py").read_text(encoding="utf-8")
        self.assertIn("/agent/copa-dos-sonhos", route_file)
        self.assertIn("/agent/dream-cup", route_file)
        self.assertIn("dream_cup.html", route_file)

    def test_agent_has_visible_game_entry_points(self):
        html = (ROOT / "app" / "templates" / "agent.html").read_text(encoding="utf-8")
        self.assertIn("/agent/copa-dos-sonhos", html)
        self.assertIn("Copa dos Sonhos", html)

    def test_database_builder_seed_and_generated_database_exist(self):
        self.assertTrue((ROOT / "scripts" / "build_dream_cup_database.py").exists())
        seed_path = ROOT / "app" / "static" / "data" / "dream_cup_seed.json"
        self.assertTrue(seed_path.exists())
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        self.assertIn("squads", seed)
        self.assertGreaterEqual(len(seed["squads"]), 10)
        squad = seed["squads"][0]
        self.assertIn("nation", squad)
        self.assertIn("year", squad)
        self.assertIn("players", squad)
        self.assertGreaterEqual(len(squad["players"]), 10)
        player = squad["players"][0]
        self.assertIn("name", player)
        self.assertIn("role", player)
        self.assertIn("role_label", player)
        self.assertIn("rating", player)

        generated_path = ROOT / "app" / "static" / "data" / "dream_cup_database.json"
        self.assertTrue(generated_path.exists(), "Rode python scripts/build_dream_cup_database.py antes dos testes completos.")
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
        self.assertIn("squads", generated)
        self.assertIn("stats", generated)
        self.assertGreaterEqual(generated["stats"].get("squads", 0), 100)
        player_count = generated["stats"].get("players") or generated["stats"].get("unique_players", 0)
        self.assertGreaterEqual(player_count, 1000)
        self.assertGreaterEqual(generated["stats"].get("squads", 0), 100)

    def test_dream_cup_js_loads_database_then_seed(self):
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        self.assertIn("dream_cup_database.json", js)
        self.assertIn("dream_cup_seed.json", js)
        self.assertIn("simulateCup", js)
        self.assertIn("playerSearch", js)

    def test_draft_is_locked_until_pick_or_limited_skip(self):
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        self.assertIn("if (state.finished || state.currentSquad) return", js)
        self.assertIn("rollBtn.disabled = Boolean(state.currentSquad)", js)
        self.assertIn("state.skips -= 1", js)
        self.assertIn("state.skips = 3", js)

    def test_tactical_positions_are_explicit_and_testable(self):
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        for function_name in (
            "compatibleSlotsForPlayer",
            "calculateTeamPower",
            "calculateOpponentPower",
            "simulateMatch",
            "positionMetrics",
            "movePlayer",
        ):
            self.assertIn(function_name, js)

        result = self.run_game_js("""({
          goalkeeper: game.compatibleSlotsForPlayer({name:'Teste', role:'GK'}),
          forward: game.compatibleSlotsForPlayer({name:'Teste', role:'FW'}),
          midfielder: game.compatibleSlotsForPlayer({name:'Teste', role:'MF'}),
          robertoCarlos: game.compatibleSlotsForPlayer({name:'Roberto Carlos', role:'DF'}),
          cafu: game.compatibleSlotsForPlayer({name:'Cafu', role:'DF'}),
          ronaldo: game.compatibleSlotsForPlayer({name:'Ronaldo', role:'FW'})
        })""")
        self.assertEqual(result["goalkeeper"], ["GK"])
        self.assertNotIn("GK", result["forward"])
        self.assertIn("CM", result["midfielder"])
        self.assertEqual(result["robertoCarlos"], ["LB", "LM"])
        self.assertEqual(result["cafu"], ["RB", "RM"])
        self.assertEqual(result["ronaldo"], ["ST"])

    def test_bad_positioning_reduces_team_power_and_seven_zero_is_rare(self):
        result = self.run_game_js("""(() => {
          const make = (role, rating=90) => ({name:'Jogador '+role, role, rating, nation:'Brasil', year:2002});
          const good = [
            {pos:'GK',player:make('GK')},{pos:'CB',player:make('DF')},{pos:'CB',player:make('DF')},
            {pos:'LB',player:make('DF')},{pos:'RB',player:make('DF')},{pos:'CM',player:make('MF')},
            {pos:'CM',player:make('MF')},{pos:'AM',player:make('MF')},{pos:'LW',player:make('FW')},
            {pos:'ST',player:make('FW')},{pos:'RW',player:make('FW')}
          ];
          const bad = good.map((slot, index) => ({...slot, pos: index === 0 ? 'ST' : index < 5 ? 'CM' : 'CB'}));
          const weak = good.map((slot) => ({...slot, player:{...slot.player, rating:72, nation:slot.pos}}));
          return {
            goodPower: game.calculateTeamPower(good, 'balanced', 0),
            badPower: game.calculateTeamPower(bad, 'balanced', 0),
            weakResult: game.simulateMatch(weak, 'balanced', 70, 0, 1)
          };
        })()""")
        self.assertGreater(result["goodPower"], result["badPower"])
        self.assertFalse(result["weakResult"]["sevenZero"])

    def test_dream_cup_layout_is_compact_and_game_focused(self):
        html = (ROOT / "app" / "templates" / "dream_cup.html").read_text(encoding="utf-8")
        css = (ROOT / "app" / "static" / "css" / "dream_cup.css").read_text(encoding="utf-8")
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        self.assertIn("optionsToggle", html)
        self.assertIn("⚙ Opções", html)
        self.assertIn("draft-board", html)
        self.assertIn("field-board", html)
        self.assertIn("summary-board", html)
        self.assertIn("pickedStat", html)
        self.assertIn("teamState", html)
        self.assertIn("draftStatus", html)
        self.assertIn("lineupStatus", html)
        self.assertIn("Deck do sorteio", html)
        self.assertIn("Placar da campanha", html)
        self.assertNotIn("database-strip", html)
        self.assertNotIn("flow-steps", html)
        self.assertIn(".game-grid", css)
        self.assertIn(".options-panel", css)
        self.assertIn(".overall-badge", css)
        self.assertIn(".slot.move-target", css)
        self.assertIn("user-select:none", css)
        self.assertIn("pickedStat", js)

    def test_player_names_and_display_labels_are_clean_and_translated(self):
        for file_name in ("dream_cup_database.json", "dream_cup_seed.json"):
            path = ROOT / "app" / "static" / "data" / file_name
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
            self.assertNotIn("not applicable", text.lower())
            for squad in data["squads"]:
                if squad.get("nation_original") == "Brazil":
                    self.assertEqual(squad["nation"], "Brasil")
                for player in squad["players"]:
                    self.assertTrue(player["name"].strip())
                    self.assertNotIn("  ", player["name"])
                    self.assertNotIn("not applicable", player["name"].lower())
                    self.assertIn(player["role"], {"GK", "DF", "MF", "FW"})
                    self.assertEqual(
                        player["role_label"],
                        {"GK": "Goleiro", "DF": "Defensor", "MF": "Meio-campista", "FW": "Atacante"}[player["role"]],
                    )
                    self.assertTrue(player.get("trait_label"))

    def test_frontend_has_portuguese_player_labels_and_no_bad_name_placeholder(self):
        html = (ROOT / "app" / "templates" / "dream_cup.html").read_text(encoding="utf-8")
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        combined = f"{html}\n{js}".lower()
        self.assertNotIn("not applicable", combined)
        self.assertIn('df: "defensor"', js.lower())
        self.assertIn('mf: "meio-campista"', js.lower())
        self.assertIn('fw: "atacante"', js.lower())
        self.assertIn('gk: "goleiro"', js.lower())
    def test_no_external_assets_or_official_images(self):
        html = (ROOT / "app" / "templates" / "dream_cup.html").read_text(encoding="utf-8")
        css = (ROOT / "app" / "static" / "css" / "dream_cup.css").read_text(encoding="utf-8")
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        combined = "\n".join([html, css, js]).lower()
        self.assertNotIn("http://", combined)
        self.assertNotIn("https://", combined)
        self.assertNotIn("autoplay", combined)
        self.assertNotIn("<audio", combined)
        self.assertNotIn("<canvas", combined)
        self.assertNotIn("nintendo", combined)

    def test_builder_mentions_attribution_and_license(self):
        builder = (ROOT / "scripts" / "build_dream_cup_database.py").read_text(encoding="utf-8")
        self.assertIn("Fjelstul World Cup Database", builder)
        self.assertIn("CC-BY-SA-4.0", builder)
        self.assertIn("squads.csv", builder)
