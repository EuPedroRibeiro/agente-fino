from __future__ import annotations

from pathlib import Path


def test_dream_cup_files_exist() -> None:
    assert Path("app/routes/dream_cup.py").exists()
    assert Path("app/templates/dream_cup.html").exists()
    assert Path("app/static/css/dream_cup.css").exists()
    assert Path("app/static/js/dream_cup.js").exists()


def test_dream_cup_has_no_external_assets_or_autoplay() -> None:
    html = Path("app/templates/dream_cup.html").read_text(encoding="utf-8").lower()
    css = Path("app/static/css/dream_cup.css").read_text(encoding="utf-8").lower()
    js = Path("app/static/js/dream_cup.js").read_text(encoding="utf-8").lower()
    combined = "\n".join([html, css, js])
    assert "http://" not in combined
    assert "https://" not in combined
    assert "cdn" not in combined
    assert "autoplay" not in combined
    assert "<audio" not in combined


def test_dream_cup_routes_are_under_agent_prefix() -> None:
    route = Path("app/routes/dream_cup.py").read_text(encoding="utf-8")
    assert '@router.get("/agent/copa-dos-sonhos"' in route
    assert '@router.get("/agent/dream-cup"' in route


def test_dream_cup_game_contains_core_loop() -> None:
    js = Path("app/static/js/dream_cup.js").read_text(encoding="utf-8")
    for keyword in ("rollSquad", "pickPlayer", "simulateTournament", "calculateChemistry", "buildCampaign"):
        assert keyword in js
