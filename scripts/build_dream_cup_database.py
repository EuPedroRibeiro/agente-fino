from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    "GK": "GK", "G": "GK", "GOALKEEPER": "GK", "GOAL KEEPER": "GK",
    "DF": "DF", "D": "DF", "DEFENDER": "DF", "FB": "DF", "CB": "DF", "LB": "DF", "RB": "DF",
    "MF": "MF", "M": "MF", "MIDFIELDER": "MF", "DM": "MF", "CM": "MF", "AM": "MF",
    "FW": "FW", "F": "FW", "FORWARD": "FW", "ST": "FW",
}
ROLE_LABELS = {"GK": "Goleiro", "DF": "Defensor", "MF": "Meio-campista", "FW": "Atacante"}
BASE_RATING = {"GK": 73, "DF": 72, "MF": 73, "FW": 74}
ROLE_TRAITS = {
    "GK": ["Reflexos", "Muralha", "Goleiro seguro", "Penalty stopper"],
    "DF": ["Zagueiro forte", "Defensive leader", "Leitura de jogo", "Combate limpo"],
    "MF": ["Playmaker", "Motor do meio", "Vertical passer", "Controle"],
    "FW": ["Finisher", "Speed", "Decisivo", "Goal threat"],
}
TEAM_TIER_BOOST = {
    "Brazil": 5, "Argentina": 4, "Germany": 4, "West Germany": 4, "France": 4,
    "Italy": 4, "Spain": 3, "Netherlands": 3, "England": 3, "Portugal": 2, "Uruguay": 2,
}
LEGEND_BOOST = {
    "pele": 18, "diego maradona": 18, "lionel messi": 17, "cristiano ronaldo": 16,
    "ronaldo": 15, "zinedine zidane": 15, "johan cruyff": 15, "franz beckenbauer": 15,
    "garrincha": 15, "romario": 14, "ronaldinho": 14, "xavi": 13, "andres iniesta": 13,
    "gianluigi buffon": 13, "lev yashin": 14, "neymar": 11, "kylian mbappe": 12,
    "luka modric": 12, "paolo maldini": 13, "roberto carlos": 13, "cafu": 11,
}
NATION_LABELS = {
    "Brazil": "Brasil", "Germany": "Alemanha", "West Germany": "Alemanha Ocidental",
    "Argentina": "Argentina", "France": "França", "Spain": "Espanha", "Italy": "Itália",
    "England": "Inglaterra", "Netherlands": "Holanda", "Portugal": "Portugal",
    "Saudi Arabia": "Arábia Saudita", "United States": "Estados Unidos",
    "South Korea": "Coreia do Sul", "Japan": "Japão", "Uruguay": "Uruguai", "Mexico": "México",
    "Croatia": "Croácia", "Belgium": "Bélgica", "Morocco": "Marrocos", "Cameroon": "Camarões",
    "Ivory Coast": "Costa do Marfim", "Ghana": "Gana", "Nigeria": "Nigéria", "Senegal": "Senegal",
    "Serbia": "Sérvia", "Switzerland": "Suíça", "Poland": "Polônia", "Denmark": "Dinamarca",
    "Sweden": "Suécia", "Russia": "Rússia", "Soviet Union": "União Soviética",
    "Czech Republic": "República Tcheca", "Czechoslovakia": "Tchecoslováquia",
    "Yugoslavia": "Iugoslávia", "Costa Rica": "Costa Rica", "Ecuador": "Equador",
    "Paraguay": "Paraguai", "Chile": "Chile", "Peru": "Peru", "Colombia": "Colômbia",
    "Wales": "País de Gales", "Scotland": "Escócia", "Northern Ireland": "Irlanda do Norte",
    "Republic of Ireland": "Irlanda", "Australia": "Austrália", "New Zealand": "Nova Zelândia",
    "Iran": "Irã", "Tunisia": "Tunísia", "Algeria": "Argélia", "Egypt": "Egito",
    "Turkey": "Turquia", "Greece": "Grécia", "Norway": "Noruega", "Austria": "Áustria",
    "Hungary": "Hungria", "Romania": "Romênia", "Bulgaria": "Bulgária",
}
TRAIT_LABELS = {
    "world cup legend": "Lenda da Copa", "lenda de copa": "Lenda da Copa",
    "lenda da copa": "Lenda da Copa", "legend": "Lenda", "star": "Craque",
    "world class": "Classe mundial", "penalty stopper": "Pegador de pênalti",
    "playmaker": "Maestro", "defensive leader": "Líder defensivo", "speed": "Velocidade",
    "vertical passer": "Passe vertical", "finisher": "Finalizador", "goal threat": "Perigo de gol",
}
EMPTY_NAME_PARTS = {"", "not applicable", "n/a", "na", "none", "null"}


def fetch_csv(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"User-Agent": "AgenteFinoDreamCupBuilder/1.0"})
    try:
        with urlopen(request, timeout=40) as response:
            raw = response.read().decode("utf-8-sig")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Falha ao baixar {url}: {exc}") from exc
    return list(csv.DictReader(raw.splitlines()))


def clean_name_part(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text.casefold() in EMPTY_NAME_PARTS:
        return ""
    text = re.sub(r"^(?:not applicable|n/?a|none|null)\s+", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def build_player_display_name(row: dict[str, str]) -> str:
    for key in ("common_name", "display_name", "player_name", "name"):
        common_name = clean_name_part(row.get(key))
        if common_name:
            return common_name
    parts = [clean_name_part(row.get("given_name")), clean_name_part(row.get("family_name"))]
    return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip() or "Jogador sem nome"


def ascii_key(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def nation_label(value: str) -> str:
    return NATION_LABELS.get(value, value)


def fallback_trait_label(rating: int) -> str:
    if rating >= 95:
        return "Lenda da Copa"
    if rating >= 90:
        return "Craque mundial"
    if rating >= 85:
        return "Destaque histórico"
    if rating >= 80:
        return "Titular confiável"
    return "Peça de elenco"


def trait_label(value: str, rating: int) -> str:
    return TRAIT_LABELS.get(ascii_key(value).strip(), fallback_trait_label(rating))


def parse_year(tournament_id: str, tournament_name: str) -> int:
    match = re.search(r"(19|20)\d{2}", f"{tournament_id} {tournament_name}")
    return int(match.group(0)) if match else 0


def is_mens_world_cup(row: dict[str, str]) -> bool:
    name = (row.get("tournament_name") or "").lower()
    tid = (row.get("tournament_id") or "").lower()
    if "women" in name or "women" in tid:
        return False
    return 1930 <= parse_year(row.get("tournament_id", ""), row.get("tournament_name", "")) <= 2022


def to_role(position_code: str, position_name: str) -> str:
    key = (position_code or "").strip().upper()
    if key in ROLE_BY_POSITION:
        return ROLE_BY_POSITION[key]
    return ROLE_BY_POSITION.get((position_name or "").strip().upper(), "MF")


def deterministic_bonus(*parts: str, limit: int = 7) -> int:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:4], 16) % (limit + 1)


def rating_for(row: dict[str, str], player_meta: dict[str, str], award_ids: set[str]) -> int:
    role = to_role(row.get("position_code", ""), row.get("position_name", ""))
    team = row.get("team_name", "")
    year = parse_year(row.get("tournament_id", ""), row.get("tournament_name", ""))
    name = build_player_display_name(row)
    rating = BASE_RATING[role] + TEAM_TIER_BOOST.get(team, 0)
    rating += deterministic_bonus(name, str(year), team, limit=8)
    try:
        rating += min(4, max(0, int(player_meta.get("count_tournaments", "")) - 1))
    except ValueError:
        pass
    if row.get("player_id", "") in award_ids:
        rating += 7
    for legend, boost in LEGEND_BOOST.items():
        if legend in ascii_key(name):
            rating += boost
            break
    rating += 1 if year >= 1998 else 0
    rating -= 1 if year <= 1954 else 0
    return max(55, min(99, rating))


def trait_for(name: str, role: str, rating: int, player_id: str) -> str:
    if rating >= 95:
        return "World Cup legend"
    if rating >= 90:
        return "World class"
    options = ROLE_TRAITS.get(role, ["Competitivo"])
    return options[deterministic_bonus(name, role, player_id, limit=len(options) - 1)]


def squad_aura(players: list[dict]) -> str:
    average = sum(player["rating"] for player in players) / max(1, len(players))
    if average >= 85:
        return "elenco histórico"
    if average >= 79:
        return "força competitiva"
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
        name = build_player_display_name(row)
        rating = rating_for(row, players.get(player_id, {}), awards)
        trait = trait_for(name, role, rating, player_id)
        shirt_raw = (row.get("shirt_number") or "").strip()
        try:
            shirt = int(float(shirt_raw)) if shirt_raw else None
        except ValueError:
            shirt = None
        player = {
            "id": player_id or hashlib.sha1(f"{team_name}-{year}-{name}".encode("utf-8")).hexdigest()[:12],
            "name": name,
            "given_name": clean_name_part(row.get("given_name")),
            "family_name": clean_name_part(row.get("family_name")),
            "role": role,
            "role_label": ROLE_LABELS[role],
            "position_code": (row.get("position_code") or role).strip() or role,
            "position_name": (row.get("position_name") or "").strip() or role,
            "shirt_number": shirt,
            "rating": rating,
            "trait": trait,
            "trait_label": trait_label(trait, rating),
            "nation_original": team_name,
            "nation": nation_label(team_name),
            "team_code": team_code,
            "year": year,
            "tournament_id": row.get("tournament_id", "").strip(),
        }
        grouped[key].append(player)
        meta_by_key[key] = {
            "nation_original": team_name,
            "nation": nation_label(team_name),
            "code": team_code,
            "year": year,
            "tournament": row.get("tournament_name", "").strip(),
            "tournament_id": row.get("tournament_id", "").strip(),
        }

    out_squads = []
    for key, players_list in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        players_list.sort(key=lambda player: (
            {"GK": 0, "DF": 1, "MF": 2, "FW": 3}.get(player["role"], 9),
            player.get("shirt_number") or 99,
            player["name"],
        ))
        meta = meta_by_key[key]
        roles = defaultdict(int)
        for player in players_list:
            roles[player["role"]] += 1
        out_squads.append({
            "id": f"{meta['code'] or meta['nation_original']}-{meta['year']}-{meta['tournament_id']}".replace(" ", "-"),
            **meta,
            "aura": squad_aura(players_list),
            "strength": round(sum(player["rating"] for player in players_list) / max(1, len(players_list)), 1),
            "roles": dict(roles),
            "players": players_list,
        })

    unique_players = {player["id"] for squad in out_squads for player in squad["players"]}
    return {
        "version": "2.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "notes": [
            "Elencos, nomes, seleções, anos, posições e números de camisa vêm da base fonte quando disponíveis.",
            "Ratings e características são derivados pelo Agente Fino para balanceamento do jogo; não são dados oficiais.",
            "O JSON é gerado para uso local/offline dentro da Copa dos Sonhos.",
        ],
        "stats": {
            "teams": len({squad["nation_original"] for squad in out_squads}),
            "squads": len(out_squads),
            "unique_players": len(unique_players),
            "players": len(unique_players),
            "squad_entries": sum(len(squad["players"]) for squad in out_squads),
        },
        "squads": out_squads,
    }


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
    print(f"- Seleções: {stats['teams']}")
    print(f"- Elencos: {stats['squads']}")
    print(f"- Jogadores únicos: {stats['unique_players']}")
    print(f"- Entradas de elenco: {stats['squad_entries']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
