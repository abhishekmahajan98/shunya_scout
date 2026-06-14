"""Predict lineups from API-Football recent match data when official sheets are unavailable."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from services import api_football
from services.formation_from_api import most_common_formation

logger = logging.getLogger(__name__)

LINEUP_CONFIDENCE = {
    "official": "Confirmed lineup",
    "predicted": "Predicted lineup (morning report)",
    "squad_fallback": "Predicted lineup — limited history (morning report)",
}


def lineup_confidence_label(source: str) -> str:
    return LINEUP_CONFIDENCE.get(source, "Predicted lineup (morning report)")


def _player_name(entry: dict) -> str:
    return str(entry.get("player", {}).get("name", "")).strip()


def _player_pos(entry: dict) -> str:
    pos = str(entry.get("player", {}).get("pos", "M")).upper()
    return pos if pos in {"G", "D", "M", "F"} else "M"


def _unavailable_names(injuries: list[dict]) -> set[str]:
    names: set[str] = set()
    for row in injuries:
        player = row.get("player", {})
        name = str(player.get("name", "")).strip()
        if name:
            names.add(name.lower())
    return names


def _suspended_from_recent_events(team_id: int, recent_rows: list[dict]) -> set[str]:
    """Flag players sent off in the most recent completed match."""
    if not recent_rows:
        return set()
    latest = recent_rows[0]
    names: set[str] = set()
    for event in latest.get("events") or []:
        if event.get("type") != "Card":
            continue
        detail = str(event.get("detail", ""))
        if detail not in {"Red Card", "Yellow Red Card"}:
            continue
        if int(event.get("team", {}).get("id", 0)) != team_id:
            continue
        name = str(event.get("player", {}).get("name", "")).strip()
        if name:
            names.add(name.lower())
    return names


def _recent_lineups_for_team(team_id: int, *, sample: int = 8) -> list[dict]:
    recent = api_football.get_team_recent_fixtures(team_id, last=10)
    if not recent:
        return []

    fixture_ids = [api_football.fixture_id_from_row(row) for row in recent[:sample]]
    detailed = api_football.get_fixtures_by_ids(fixture_ids)
    lineups: list[dict] = []
    for row in detailed:
        for lineup in row.get("lineups") or []:
            if int(lineup.get("team", {}).get("id", 0)) == team_id:
                if lineup.get("startXI"):
                    lineups.append(lineup)
    return lineups


def _formation_slots(formation: str) -> tuple[int, int, int]:
    parts = [int(part) for part in formation.split("-") if part.isdigit()]
    if len(parts) >= 3:
        return parts[0], parts[1], sum(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], 1
    return 4, 3, 3


def _position_counts(recent_lineups: list[dict]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {
        "G": Counter(),
        "D": Counter(),
        "M": Counter(),
        "F": Counter(),
    }
    for lineup in recent_lineups:
        for entry in lineup.get("startXI") or []:
            name = _player_name(entry)
            if not name:
                continue
            counts[_player_pos(entry)][name] += 1
    return counts


def _pick_top(
    counter: Counter[str],
    count: int,
    *,
    unavailable: set[str],
    picked: set[str],
) -> list[str]:
    selected: list[str] = []
    for name, _ in counter.most_common():
        if name.lower() in unavailable:
            continue
        if name.lower() in {item.lower() for item in picked}:
            continue
        selected.append(name)
        picked.add(name)
        if len(selected) >= count:
            break
    return selected


def _pick_replacement(
    pos: str,
    *,
    squad_names: list[str],
    counts: dict[str, Counter[str]],
    unavailable: set[str],
    already_picked: set[str],
) -> str | None:
    candidates = list(counts.get(pos, Counter()).elements())
    for name in squad_names:
        if name not in candidates:
            candidates.append(name)
    scored: list[tuple[int, str]] = []
    for name in candidates:
        if name.lower() in unavailable:
            continue
        if name.lower() in {picked.lower() for picked in already_picked}:
            continue
        scored.append((counts.get(pos, Counter()).get(name, 0), name))
    if not scored:
        return None
    return max(scored, key=lambda item: item[0])[1]


def _build_frequency_xi(
    recent_lineups: list[dict],
    *,
    unavailable: set[str],
    squad_names: list[str],
) -> tuple[list[dict], str]:
    counts = _position_counts(recent_lineups)
    formation = most_common_formation(recent_lineups)
    defenders, mids, forwards = _formation_slots(formation)
    picked_names: set[str] = set()
    slots = [
        ("G", 1),
        ("D", defenders),
        ("M", mids),
        ("F", forwards),
    ]
    start_xi: list[dict] = []
    for pos, needed in slots:
        names = _pick_top(
            counts[pos],
            needed,
            unavailable=unavailable,
            picked=picked_names,
        )
        while len(names) < needed:
            replacement = _pick_replacement(
                pos,
                squad_names=squad_names,
                counts=counts,
                unavailable=unavailable,
                already_picked=picked_names,
            )
            if not replacement:
                break
            names.append(replacement)
            picked_names.add(replacement)
        for name in names:
            start_xi.append({"player": {"name": name, "pos": pos, "grid": None}})
            picked_names.add(name)

    if len(start_xi) == 11:
        return start_xi, formation
    return [], formation


def _squad_position(pos: str) -> str:
    lowered = pos.lower()
    if "goal" in lowered:
        return "G"
    if "def" in lowered:
        return "D"
    if "mid" in lowered:
        return "M"
    if "att" in lowered or "for" in lowered or "strik" in lowered:
        return "F"
    return "M"


def predict_team_lineup(
    team_id: int,
    team_name: str,
    *,
    unavailable: set[str],
    recent_rows: list[dict] | None = None,
) -> dict:
    recent_lineups = _recent_lineups_for_team(team_id)
    squad = api_football.get_squad(team_id)
    squad_names = [str(p.get("name", "")).strip() for p in squad if p.get("name")]

    if recent_rows is None:
        recent_rows = api_football.get_team_recent_fixtures(team_id, last=3)
    suspended = _suspended_from_recent_events(team_id, recent_rows)
    unavailable = unavailable | suspended

    start_xi, formation = _build_frequency_xi(
        recent_lineups,
        unavailable=unavailable,
        squad_names=squad_names,
    )
    if len(start_xi) == 11:
        return {
            "team": {"id": team_id, "name": team_name},
            "formation": formation,
            "startXI": start_xi,
            "source": "predicted",
        }

    if not squad_names:
        return {
            "team": {"id": team_id, "name": team_name},
            "formation": "4-3-3",
            "startXI": [],
            "source": "empty",
        }

    by_pos: dict[str, list[str]] = defaultdict(list)
    for player in squad:
        name = str(player.get("name", "")).strip()
        if not name or name.lower() in unavailable:
            continue
        pos = _squad_position(str(player.get("position", "M")))
        by_pos[pos].append(name)

    formation = "4-3-3"
    defenders, mids, forwards = _formation_slots(formation)
    layout = [("F", forwards), ("M", mids), ("D", defenders), ("G", 1)]
    fallback_xi: list[dict] = []
    for pos, count in layout:
        for name in by_pos[pos][:count]:
            fallback_xi.append({"player": {"name": name, "pos": pos, "grid": None}})

    logger.warning(
        "Limited lineup history for %s — built from squad roster",
        team_name,
    )
    return {
        "team": {"id": team_id, "name": team_name},
        "formation": formation,
        "startXI": fallback_xi[:11],
        "source": "squad_fallback",
    }


def recent_suspension_names(team_id: int, recent_rows: list[dict]) -> set[str]:
    return _suspended_from_recent_events(team_id, recent_rows)


def resolve_match_lineups(
    *,
    fixture_id: int,
    team_a_id: int,
    team_b_id: int,
    team_a_name: str,
    team_b_name: str,
) -> tuple[dict, dict, str]:
    """Return (team_a_lineup, team_b_lineup, source_label)."""
    injuries = api_football.get_injuries(fixture_id=fixture_id)
    unavailable = _unavailable_names(injuries)

    official = api_football.get_lineups(fixture_id)
    if official:
        by_team = {int(item.get("team", {}).get("id", 0)): item for item in official}
        team_a_lineup = by_team.get(team_a_id)
        team_b_lineup = by_team.get(team_b_id)
        if (
            team_a_lineup
            and team_b_lineup
            and len(team_a_lineup.get("startXI") or []) == 11
            and len(team_b_lineup.get("startXI") or []) == 11
        ):
            team_a_lineup["source"] = "official"
            team_b_lineup["source"] = "official"
            return team_a_lineup, team_b_lineup, "official"

    recent_a = api_football.get_team_recent_fixtures(team_a_id, last=3)
    recent_b = api_football.get_team_recent_fixtures(team_b_id, last=3)
    team_a_lineup = predict_team_lineup(
        team_a_id,
        team_a_name,
        unavailable=unavailable,
        recent_rows=recent_a,
    )
    team_b_lineup = predict_team_lineup(
        team_b_id,
        team_b_name,
        unavailable=unavailable,
        recent_rows=recent_b,
    )
    source = "predicted"
    if (
        team_a_lineup.get("source") == "squad_fallback"
        or team_b_lineup.get("source") == "squad_fallback"
    ):
        source = "squad_fallback"
    return team_a_lineup, team_b_lineup, source
