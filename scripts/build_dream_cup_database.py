from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "app" / "static" / "data"
OUT_FILE = OUT_DIR / "dream_cup_database.json"

DATAHUB_BASE = "https://datahub.io/football/worldcup/_r/-/"
SQUADS_URL = DATAHUB_BASE + "squads.csv"
PLAYERS_URL = DATAHUB_BASE + "players.csv"
AWARDS_URL = DATAHUB_BASE + "award_winners.csv"

SOURCE_NAME = "Fjelstul World Cup Database via DataHub"
SOURCE_URL = "https://datahub.io/football/worldcup"
LICENSE = "CC-BY-SA-4.0"
ATTRIBUTION = "Joshua C. Fjelstul, Ph.D. / DataHub football/worldcup"

ROLE_BY_POSITION = {
    "GK": "GK",
    "G": "GK",
    "GOALKEEPER": "GK",
    "GOAL KEEPER": "GK",
    "DF": "DF",
    "D": "DF",
    "DEFENDER": "DF",
    "FB": "DF",
    "CB": "DF",
    "LB": "DF",
    "RB": "DF",
    "MF": "MF",
    "M": "MF",
    "MIDFIELDER": "MF",
    "DM": "MF",
    "CM": "MF",
    "AM": "MF",
    "FW": "FW",
    "F": "FW",
    "FORWARD": "FW",
    "ST": "FW",
}

BASE_RATING = {"GK": 73, "DF": 72, "MF": 73, "FW": 74}
ROLE_TRAITS = {
    "GK": ["Reflexos", "Muralha", "Goleiro seguro", "Pegador de penaltis"],
    "DF": ["Zagueiro forte", "Lider defensivo", "Leitura de jogo", "Combate limpo"],
    "MF": ["Maestro", "Motor do meio", "Passe vertical", "Controle"],
    "FW": ["Finalizador", "Velocidade", "Decisivo", "Atacante tecnico"],
}
TEAM_TIER_BOOST = {
    "Brazil": 5,
    "Argentina": 4,
    "Germany": 4,
    "West Germany": 4,
    "France": 4,
    "Italy": 4,
    "Spain": 3,
    "Netherlands": 3,
    "England": 3,
    "Portugal": 2,
    "Uruguay": 2,
}
LEGEND_BOOST = {
    "pele": 18,
    "diego maradona": 18,
    "lionel messi": 17,
    "cristiano ronaldo": 16,
    "ronaldo": 15,
    "zinedine zidane": 15,
    "johan cruyff": 15,
    "franz beckenbauer": 15,
    "garrincha": 15,
    "romario": 14,
    "ronaldinho": 14,
    "xavi": 13,
    "andres iniesta": 13,
    "gianluigi buffon": 13,
    "lev yashin": 14,
    "neymar": 11,
    "kylian mbappe": 12,
    "luka modric": 12,
    "paolo maldini": 13,
    "roberto carlos": 13,
    "cafú": 11,
    "cafu": 11,
}

def fetch_csv(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"User-Agent": "AgenteFinoDreamCupBuilder/1.0"})
    try:
        with urlopen(request, timeout=40) as response:
            raw = response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Falha ao baixar {url}: {exc}") from exc
    return list(csv.DictReader(raw.splitlines()))

def normalize_name(given: str | None, family: str | None) -> str:
    given = (given or "").strip()
    family = (family or "").strip()
    name = " ".join(part for part in [given, family] if part).strip()
    return re.sub(r"\s+", " ", name) or family or given or "Jogador"

def ascii_key(value: str) -> str:
    replacements = str.maketrans({
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ò": "o", "õ": "o", "ô": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c", "ñ": "n",
    })
    return value.lower().translate(replacements)

def parse_year(tournament_id: str, tournament_name: str) -> int:
    text = f"{tournament_id} {tournament_name}"
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return 0
    return int(match.group(0))

def is_mens_world_cup(row: dict[str, str]) -> bool:
    name = (row.get("tournament_name") or "").lower()
    tid = (row.get("tournament_id") or "").lower()
    if "women" in name or "women" in tid:
        return False
    year = parse_year(row.get("tournament_id", ""), row.get("tournament_name", ""))
    return 1930 <= year <= 2022

def to_role(position_code: str, position_name: str) -> str:
    key = (position_code or "").strip().upper()
    if key in ROLE_BY_POSITION:
        return ROLE_BY_POSITION[key]
    return ROLE_BY_POSITION.get((position_name or "").strip().upper(), "MF")

def deterministic_bonus(*parts: str, limit: int = 7) -> int:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return int(h[:4], 16) % (limit + 1)

def rating_for(row: dict[str, str], player_meta: dict[str, str], award_ids: set[str]) -> int:
    role = to_role(row.get("position_code", ""), row.get("position_name", ""))
    team = row.get("team_name", "")
    year = parse_year(row.get("tournament_id", ""), row.get("tournament_name", ""))
    name = normalize_name(row.get("given_name"), row.get("family_name"))
    key = ascii_key(name)

    rating = BASE_RATING[role]
    rating += TEAM_TIER_BOOST.get(team, 0)
    rating += deterministic_bonus(name, str(year), team, limit=8)

    count_tournaments = player_meta.get("count_tournaments", "")
    try:
        rating += min(4, max(0, int(count_tournaments) - 1))
    except ValueError:
        pass

    if row.get("player_id", "") in award_ids:
        rating += 7

    for legend, boost in LEGEND_BOOST.items():
        if legend in key:
            rating += boost
            break

    if year >= 1998:
        rating += 1
    if year <= 1954:
        rating -= 1

    return max(55, min(99, rating))

def trait_for(name: str, role: str, rating: int, player_id: str) -> str:
    if rating >= 95:
        return "Lenda de Copa"
    if rating >= 90:
        return "Craque mundial"
    options = ROLE_TRAITS.get(role, ["Competitivo"])
    idx = deterministic_bonus(name, role, player_id, limit=len(options) - 1)
    return options[idx]

def squad_aura(players: list[dict]) -> str:
    avg = sum(p["rating"] for p in players) / max(1, len(players))
    if avg >= 85:
        return "elenco historico"
    if avg >= 79:
        return "forca competitiva"
    return "zebra perigosa"

def build_database() -> dict:
    squads = fetch_csv(SQUADS_URL)
    try:
        players = {row.get("player_id", ""): row for row in fetch_csv(PLAYERS_URL)}
    except RuntimeError:
        players = {}
    try:
        awards = {row.get("player_id", "") for row in fetch_csv(AWARDS_URL) if row.get("player_id")}
    except RuntimeError:
        awards = set()

    grouped: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    meta_by_key: dict[tuple[str, int, str], dict] = {}

    for row in squads:
        if not is_mens_world_cup(row):
            continue
        year = parse_year(row.get("tournament_id", ""), row.get("tournament_name", ""))
        if not year:
            continue
        team_name = row.get("team_name", "").strip()
        team_code = row.get("team_code", "").strip()
        key = (team_name, year, row.get("tournament_id", "").strip())
        player_id = row.get("player_id", "").strip()
        role = to_role(row.get("position_code", ""), row.get("position_name", ""))
        name = normalize_name(row.get("given_name"), row.get("family_name"))
        player_meta = players.get(player_id, {})
        rating = rating_for(row, player_meta, awards)
        shirt_raw = (row.get("shirt_number") or "").strip()
        try:
            shirt = int(float(shirt_raw)) if shirt_raw else None
        except ValueError:
            shirt = None
        player = {
            "id": player_id or hashlib.sha1(f"{team_name}-{year}-{name}".encode("utf-8")).hexdigest()[:12],
            "name": name,
            "given_name": (row.get("given_name") or "").strip(),
            "family_name": (row.get("family_name") or "").strip(),
            "role": role,
            "position_code": (row.get("position_code") or role).strip() or role,
            "position_name": (row.get("position_name") or "").strip() or role,
            "shirt_number": shirt,
            "rating": rating,
            "trait": trait_for(name, role, rating, player_id),
            "nation": team_name,
            "team_code": team_code,
            "year": year,
            "tournament_id": row.get("tournament_id", "").strip(),
        }
        grouped[key].append(player)
        meta_by_key[key] = {
            "nation": team_name,
            "code": team_code,
            "year": year,
            "tournament": row.get("tournament_name", "").strip(),
            "tournament_id": row.get("tournament_id", "").strip(),
        }

    out_squads = []
    for key, players_list in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        players_list.sort(key=lambda p: ({"GK": 0, "DF": 1, "MF": 2, "FW": 3}.get(p["role"], 9), p.get("shirt_number") or 99, p["name"]))
        meta = meta_by_key[key]
        roles = defaultdict(int)
        for p in players_list:
            roles[p["role"]] += 1
        strength = round(sum(p["rating"] for p in players_list) / max(1, len(players_list)), 1)
        out_squads.append({
            "id": f"{meta['code'] or meta['nation']}-{meta['year']}-{meta['tournament_id']}".replace(" ", "-"),
            **meta,
            "aura": squad_aura(players_list),
            "strength": strength,
            "roles": dict(roles),
            "players": players_list,
        })

    unique_players = {p["id"] for squad in out_squads for p in squad["players"]}
    unique_teams = {s["nation"] for s in out_squads}
    database = {
        "version": "2.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "notes": [
            "Elencos, nomes, selecoes, anos, posicoes e numeros de camisa vêm da base fonte quando disponíveis.",
            "Ratings e traits são derivados pelo Agente Fino para balanceamento do jogo; não são dados oficiais.",
            "O JSON é gerado para uso local/offline dentro da Copa dos Sonhos."
        ],
        "stats": {
            "teams": len(unique_teams),
            "squads": len(out_squads),
            "unique_players": len(unique_players),
            "players": len(unique_players),
            "squad_entries": sum(len(s["players"]) for s in out_squads),
        },
        "squads": out_squads,
    }
    return database

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        database = build_database()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    OUT_FILE.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = database["stats"]
    print("Dream Cup database gerado com sucesso:")
    print(f"- Arquivo: {OUT_FILE}")
    print(f"- Selecoes: {stats['teams']}")
    print(f"- Elencos: {stats['squads']}")
    print(f"- Jogadores unicos: {stats['unique_players']}")
    print(f"- Entradas de elenco: {stats['squad_entries']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
