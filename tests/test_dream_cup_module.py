from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class DreamCupModuleTests(TestCase):
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
        self.assertIn("rating", player)

        generated_path = ROOT / "app" / "static" / "data" / "dream_cup_database.json"
        self.assertTrue(generated_path.exists(), "Rode python scripts/build_dream_cup_database.py antes dos testes completos.")
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
        self.assertIn("squads", generated)
        self.assertIn("stats", generated)
        self.assertGreaterEqual(generated["stats"].get("squads", 0), 100)
        player_count = generated["stats"].get("players") or generated["stats"].get("unique_players", 0)
        self.assertGreaterEqual(player_count, 1000)

    def test_dream_cup_js_loads_database_then_seed(self):
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        self.assertIn("dream_cup_database.json", js)
        self.assertIn("dream_cup_seed.json", js)
        self.assertIn("simulateCup", js)
        self.assertIn("playerSearch", js)


    def test_dream_cup_v3_layout_has_clear_three_zone_flow(self):
        html = (ROOT / "app" / "templates" / "dream_cup.html").read_text(encoding="utf-8")
        css = (ROOT / "app" / "static" / "css" / "dream_cup.css").read_text(encoding="utf-8")
        js = (ROOT / "app" / "static" / "js" / "dream_cup.js").read_text(encoding="utf-8")
        self.assertIn("dream-cup-v3", html)
        self.assertIn("flow-steps", html)
        self.assertIn("summary-board", html)
        self.assertIn("pickedStat", html)
        self.assertIn("teamState", html)
        self.assertIn("Copa dos Sonhos v3", css)
        self.assertIn("choose-badge", css)
        self.assertIn("pickedStat", js)
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
