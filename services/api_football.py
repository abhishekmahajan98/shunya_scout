"""API-Football (api-sports) client for structured match facts."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"
COMPLETED_STATUSES = frozenset({"FT", "AET", "PEN"})

_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_DEFAULT_CACHE_TTL = 3600


def _require_key() -> str:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        raise ValueError("API_FOOTBALL_KEY environment variable is not set")
    return key


def world_cup_league_id() -> int:
    raw = os.environ.get("WORLD_CUP_LEAGUE_ID", "1").strip()
    try:
        return int(raw)
    except ValueError:
        return 1


def world_cup_season() -> int:
    raw = os.environ.get("WORLD_CUP_SEASON", "2026").strip()
    try:
        return int(raw)
    except ValueError:
        return 2026


def _cache_get(key: str) -> Any | None:
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            return None
        return value


def _cache_set(key: str, value: Any, *, ttl: int = _DEFAULT_CACHE_TTL) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic() + ttl, value)


def _request(path: str, params: dict[str, Any] | None = None) -> list[dict]:
    cache_key = f"{path}:{params}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {"x-apisports-key": _require_key()}
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{BASE_URL}{path}", headers=headers, params=params or {})
    response.raise_for_status()
    payload = response.json()

    errors = payload.get("errors")
    if errors:
        logger.warning("API-Football errors for %s: %s", path, errors)

    data = payload.get("response") or []
    if not isinstance(data, list):
        data = [data] if data else []

    _cache_set(cache_key, data)
    return data


def get_fixtures_for_date(report_date: str) -> list[dict]:
    return _request(
        "/fixtures",
        {
            "league": world_cup_league_id(),
            "season": world_cup_season(),
            "date": report_date,
            "timezone": "UTC",
        },
    )


def get_fixture(fixture_id: int) -> dict | None:
    rows = _request("/fixtures", {"id": fixture_id})
    return rows[0] if rows else None


def get_fixtures_by_ids(fixture_ids: list[int]) -> list[dict]:
    if not fixture_ids:
        return []
    chunks: list[list[int]] = []
    for index in range(0, len(fixture_ids), 20):
        chunks.append(fixture_ids[index : index + 20])
    results: list[dict] = []
    for chunk in chunks:
        ids_param = "-".join(str(fixture_id) for fixture_id in chunk)
        results.extend(_request("/fixtures", {"ids": ids_param}))
    return results


def get_lineups(fixture_id: int) -> list[dict]:
    return _request("/fixtures/lineups", {"fixture": fixture_id})


def get_team_recent_fixtures(team_id: int, *, last: int = 10) -> list[dict]:
    cache_key = f"team_recent:{team_id}:{last}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    rows = _request("/fixtures", {"team": team_id, "last": last})
    completed = [
        row
        for row in rows
        if row.get("fixture", {}).get("status", {}).get("short") in COMPLETED_STATUSES
    ]
    _cache_set(cache_key, completed, ttl=1800)
    return completed


def get_h2h(team_a_id: int, team_b_id: int, *, last: int = 10) -> list[dict]:
    return _request(
        "/fixtures/headtohead",
        {"h2h": f"{team_a_id}-{team_b_id}", "last": last},
    )


def get_squad(team_id: int) -> list[dict]:
    cache_key = f"squad:{team_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    rows = _request("/players/squads", {"team": team_id})
    players = rows[0].get("players", []) if rows else []
    _cache_set(cache_key, players, ttl=86400)
    return players


def get_injuries(
    *,
    fixture_id: int | None = None,
    team_id: int | None = None,
) -> list[dict]:
    params: dict[str, Any] = {
        "league": world_cup_league_id(),
        "season": world_cup_season(),
    }
    if fixture_id is not None:
        params["fixture"] = fixture_id
    if team_id is not None:
        params["team"] = team_id
    return _request("/injuries", params)


def get_fixture_players(fixture_id: int) -> list[dict]:
    return _request("/fixtures/players", {"fixture": fixture_id})


def get_standings() -> list[dict]:
    cache_key = f"standings:{world_cup_league_id()}:{world_cup_season()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    rows = _request(
        "/standings",
        {"league": world_cup_league_id(), "season": world_cup_season()},
    )
    _cache_set(cache_key, rows, ttl=3600)
    return rows


def get_predictions(fixture_id: int) -> dict | None:
    rows = _request("/predictions", {"fixture": fixture_id})
    return rows[0] if rows else None


def get_odds(fixture_id: int) -> list[dict]:
    return _request("/odds", {"fixture": fixture_id})


def get_fixture_events(fixture_id: int) -> list[dict]:
    return _request("/fixtures/events", {"fixture": fixture_id})


def get_fixture_statistics(fixture_id: int) -> list[dict]:
    return _request("/fixtures/statistics", {"fixture": fixture_id})


def fixture_id_from_row(row: dict) -> int:
    return int(row["fixture"]["id"])


def team_name(row: dict, *, home: bool) -> str:
    key = "home" if home else "away"
    return str(row["teams"][key]["name"])


def team_id_from_row(row: dict, *, home: bool) -> int:
    key = "home" if home else "away"
    return int(row["teams"][key]["id"])


def score_string(row: dict) -> str:
    goals = row.get("goals", {})
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return "—"
    return f"{home}-{away}"


def result_for_team(row: dict, team_id: int) -> str:
    goals = row.get("goals", {})
    home_id = team_id_from_row(row, home=True)
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return "?"
    if home == away:
        return "D"
    if team_id == home_id:
        return "W" if home > away else "L"
    return "W" if away > home else "L"


def opponent_for_team(row: dict, team_id: int) -> str:
    home_id = team_id_from_row(row, home=True)
    if team_id == home_id:
        return team_name(row, home=False)
    return team_name(row, home=True)


def venue_label(row: dict, team_id: int) -> str:
    home_id = team_id_from_row(row, home=True)
    return "H" if team_id == home_id else "A"


def kickoff_label(row: dict) -> str:
    fixture = row.get("fixture", {})
    date = fixture.get("date", "")
    venue = row.get("venue", {}) or {}
    name = venue.get("name") or "TBD"
    city = venue.get("city") or ""
    location = f"{name}, {city}" if city else name
    return f"{date} — {location}" if date else location


def stage_label(row: dict) -> str:
    league = row.get("league", {})
    round_name = league.get("round") or ""
    if round_name:
        return round_name
    return league.get("name") or "FIFA World Cup"
