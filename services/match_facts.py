"""Gather structured match facts from API-Football and format as scout research."""

from __future__ import annotations

import logging

from models.state import Match
from services import api_football
from services.formation_from_api import build_formation_block
from services.lineup_predict import resolve_match_lineups
from utils.slug import match_slug

logger = logging.getLogger(__name__)


def _injuries_summary(injuries: list[dict]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for row in injuries:
        player = row.get("player", {})
        team = row.get("team", {})
        name = str(player.get("name", "")).strip()
        if not name:
            continue
        key = f"{team.get('name')}:{name}"
        if key in seen:
            continue
        seen.add(key)
        reason = str(row.get("type") or row.get("reason") or "out").strip()
        parts.append(f"{team.get('name', 'Team')}: {name} ({reason})")
    return "; ".join(parts)


def _format_injuries(injuries: list[dict]) -> str:
    if not injuries:
        return "No injuries or suspensions reported in API-Football."
    lines: list[str] = []
    seen: set[str] = set()
    for row in injuries:
        player = row.get("player", {})
        team = row.get("team", {})
        name = str(player.get("name", "")).strip()
        if not name:
            continue
        key = f"{team.get('name')}:{name}"
        if key in seen:
            continue
        seen.add(key)
        reason = str(row.get("type") or row.get("reason") or "unavailable").strip()
        lines.append(f"- **{team.get('name', 'Team')}** — {name}: {reason}")
    return "\n".join(lines)


def _format_standings_context(team_a: str, team_b: str) -> str:
    rows = api_football.get_standings()
    if not rows:
        return "Standings not yet available in API-Football."

    league = rows[0].get("league", {})
    groups = league.get("standings") or []
    if not groups:
        return "Standings not yet available in API-Football."

    lines = [f"**{league.get('name', 'World Cup')} — {league.get('season', '')}**", ""]
    target_names = {team_a.lower(), team_b.lower()}
    for group in groups:
        group_lines: list[str] = []
        for entry in group:
            team = entry.get("team", {})
            name = str(team.get("name", ""))
            if name.lower() not in target_names:
                continue
            stats = entry.get("all", {})
            group_lines.append(
                f"- **{name}**: rank {entry.get('rank')}, "
                f"{entry.get('points')} pts, GD {entry.get('goalsDiff')}, "
                f"form {entry.get('form', '—')}, "
                f"played {stats.get('played', '—')} "
                f"({stats.get('win', 0)}W-{stats.get('draw', 0)}D-{stats.get('lose', 0)}L)"
            )
        if group_lines:
            lines.extend(group_lines)
            lines.append("")

    if len(lines) <= 2:
        return "Neither team found in current World Cup standings table."
    return "\n".join(lines).strip()


def _stat_value(team_stats: dict, stat_type: str) -> str | None:
    for item in team_stats.get("statistics") or []:
        if item.get("type") == stat_type:
            return str(item.get("value", ""))
    return None


def _format_match_stats(row: dict, team_id: int) -> str:
    for block in row.get("statistics") or []:
        if int(block.get("team", {}).get("id", 0)) != team_id:
            continue
        possession = _stat_value(block, "Ball Possession")
        shots = _stat_value(block, "Total Shots")
        on_target = _stat_value(block, "Shots on Goal")
        corners = _stat_value(block, "Corner Kicks")
        parts = [
            part
            for part in (
                f"Possession {possession}" if possession else "",
                f"Shots {shots}" if shots else "",
                f"On target {on_target}" if on_target else "",
                f"Corners {corners}" if corners else "",
            )
            if part
        ]
        return ", ".join(parts)
    return ""


def _format_match_events(row: dict, team_id: int) -> str:
    goals: list[str] = []
    cards: list[str] = []
    for event in row.get("events") or []:
        if int(event.get("team", {}).get("id", 0)) != team_id:
            continue
        minute = event.get("time", {}).get("elapsed", "?")
        extra = event.get("time", {}).get("extra")
        time_label = f"{minute}+{extra}" if extra else str(minute)
        player = event.get("player", {}).get("name", "?")
        if event.get("type") == "Goal":
            detail = event.get("detail", "Goal")
            assist = event.get("assist", {}).get("name")
            label = f"{player} {time_label}'"
            if assist:
                label += f" (assist {assist})"
            if detail != "Normal Goal":
                label += f" [{detail}]"
            goals.append(label)
        elif event.get("type") == "Card":
            cards.append(f"{player} {time_label}' ({event.get('detail', 'Card')})")
    parts: list[str] = []
    if goals:
        parts.append("Goals: " + "; ".join(goals))
    if cards:
        parts.append("Cards: " + "; ".join(cards))
    return " | ".join(parts)


def _format_suspensions(team_id: int, team_name: str, recent_rows: list[dict]) -> str:
    from services.lineup_predict import recent_suspension_names

    suspended = recent_suspension_names(team_id, recent_rows)
    if not suspended:
        return f"No recent red-card suspensions flagged for {team_name}."
    names = ", ".join(sorted(suspended))
    return (
        f"**{team_name}** — players sent off in last match (likely unavailable): {names}"
    )


def _format_recent_form(team_id: int, team_name: str) -> str:
    recent = api_football.get_team_recent_fixtures(team_id, last=10)
    if not recent:
        return f"No recent completed fixtures found for {team_name}."

    fixture_ids = [api_football.fixture_id_from_row(row) for row in recent]
    detailed = {api_football.fixture_id_from_row(row): row for row in api_football.get_fixtures_by_ids(fixture_ids)}

    wins = draws = losses = 0
    goals_for = goals_against = 0
    lines = [f"### {team_name} — last {len(recent)} completed games", ""]

    for index, summary in enumerate(reversed(recent), start=1):
        fixture_id = api_football.fixture_id_from_row(summary)
        row = detailed.get(fixture_id, summary)
        opponent = api_football.opponent_for_team(row, team_id)
        venue = api_football.venue_label(row, team_id)
        score = api_football.score_string(row)
        result = api_football.result_for_team(row, team_id)
        date = row.get("fixture", {}).get("date", "")[:10]
        competition = row.get("league", {}).get("name", "Competition")
        round_name = row.get("league", {}).get("round", "")

        goals = row.get("goals", {})
        home_id = api_football.team_id_from_row(row, home=True)
        if team_id == home_id:
            gf, ga = goals.get("home"), goals.get("away")
        else:
            gf, ga = goals.get("away"), goals.get("home")
        if gf is not None and ga is not None:
            goals_for += gf
            goals_against += ga

        if result == "W":
            wins += 1
        elif result == "D":
            draws += 1
        else:
            losses += 1

        formation = ""
        for lineup in row.get("lineups") or []:
            if int(lineup.get("team", {}).get("id", 0)) == team_id:
                formation = str(lineup.get("formation") or "")
                starters = [
                    p.get("player", {}).get("name", "")
                    for p in lineup.get("startXI") or []
                ]
                if starters:
                    formation = f"{formation} — {', '.join(starters[:11])}"
                break

        context = f" ({round_name})" if round_name else ""
        lines.append(
            f"{index}. {date} — {competition}{context} vs {opponent} "
            f"({venue}) **{score}** [{result}]"
        )
        if formation:
            lines.append(f"   - Lineup: {formation}")
        stats_line = _format_match_stats(row, team_id)
        if stats_line:
            lines.append(f"   - Stats: {stats_line}")
        events_line = _format_match_events(row, team_id)
        if events_line:
            lines.append(f"   - Events: {events_line}")

    lines.extend(
        [
            "",
            f"**Summary:** {wins}W-{draws}D-{losses}L, "
            f"goals {goals_for}-{goals_against}",
        ]
    )
    return "\n".join(lines)


def _format_h2h(team_a_id: int, team_b_id: int, team_a: str, team_b: str) -> str:
    meetings = api_football.get_h2h(team_a_id, team_b_id, last=10)
    if not meetings:
        return f"No head-to-head history found between {team_a} and {team_b}."

    wins_a = wins_b = draws = 0
    lines = [f"**{team_a} vs {team_b}** — last {len(meetings)} meetings", ""]
    for row in meetings:
        home = api_football.team_name(row, home=True)
        away = api_football.team_name(row, home=False)
        score = api_football.score_string(row)
        date = row.get("fixture", {}).get("date", "")[:10]
        competition = row.get("league", {}).get("name", "")
        lines.append(f"- {date} — {competition}: {home} {score} {away}")

        result_a = api_football.result_for_team(row, team_a_id)
        if result_a == "W":
            wins_a += 1
        elif result_a == "D":
            draws += 1
        else:
            wins_b += 1

    lines.extend(
        [
            "",
            f"**H2H record ({team_a} perspective):** "
            f"{wins_a}W-{draws}D-{wins_b}L over sampled meetings",
        ]
    )
    return "\n".join(lines)


def _format_squads(team_a_id: int, team_b_id: int, team_a: str, team_b: str) -> str:
    lines = []
    for team_id, name in ((team_a_id, team_a), (team_b_id, team_b)):
        squad = api_football.get_squad(team_id)
        lines.append(f"### {name} squad ({len(squad)} players)")
        if not squad:
            lines.append("Squad not available.")
            lines.append("")
            continue
        for player in squad:
            lines.append(
                f"- {player.get('name')} "
                f"({player.get('position', '?')}, #{player.get('number', '?')})"
            )
        lines.append("")
    return "\n".join(lines).strip()


def _format_player_form(team_id: int, team_name: str) -> str:
    recent = api_football.get_team_recent_fixtures(team_id, last=5)
    if not recent:
        return f"No recent player data for {team_name}."

    ratings: list[tuple[str, float, int]] = []
    goals: list[tuple[str, int]] = []
    assists: list[tuple[str, int]] = []

    for summary in recent:
        fixture_id = api_football.fixture_id_from_row(summary)
        for block in api_football.get_fixture_players(fixture_id):
            if int(block.get("team", {}).get("id", 0)) != team_id:
                continue
            for entry in block.get("players") or []:
                player = entry.get("player", {})
                stats = entry.get("statistics") or [{}]
                stat = stats[0] if stats else {}
                name = str(player.get("name", "")).strip()
                if not name:
                    continue
                rating_raw = stat.get("games", {}).get("rating")
                if rating_raw:
                    try:
                        ratings.append((name, float(rating_raw), fixture_id))
                    except (TypeError, ValueError):
                        pass
                g = stat.get("goals", {}).get("total")
                a = stat.get("goals", {}).get("assists")
                if g:
                    goals.append((name, int(g)))
                if a:
                    assists.append((name, int(a)))

    lines = [f"### {team_name}", ""]
    if ratings:
        top = sorted(ratings, key=lambda item: item[1], reverse=True)[:5]
        lines.append("**Top ratings (recent matches):**")
        for name, rating, _ in top:
            lines.append(f"- {name}: {rating:.1f}")
        lines.append("")
    if goals:
        lines.append("**Goals:**")
        for name, count in sorted(goals, key=lambda item: item[1], reverse=True)[:5]:
            lines.append(f"- {name}: {count}")
        lines.append("")
    if assists:
        lines.append("**Assists:**")
        for name, count in sorted(assists, key=lambda item: item[1], reverse=True)[:5]:
            lines.append(f"- {name}: {count}")

    if len(lines) <= 2:
        return f"No player performance stats available for {team_name}."
    return "\n".join(lines)


def _format_predictions(fixture_id: int) -> str:
    prediction = api_football.get_predictions(fixture_id)
    if not prediction:
        return "Predictions not available from API-Football."

    pred = prediction.get("predictions", {})
    comparison = prediction.get("comparison", {})
    percent = pred.get("percent", {})
    lines = [
        f"- **Predicted winner:** {pred.get('winner', {}).get('name', '—')} "
        f"({pred.get('winner', {}).get('comment', '')})",
        f"- **Advice:** {pred.get('advice', '—')}",
        f"- **Win probabilities:** home {percent.get('home', '—')}, "
        f"draw {percent.get('draw', '—')}, away {percent.get('away', '—')}",
        f"- **Goals forecast:** home {pred.get('goals', {}).get('home', '—')}, "
        f"away {pred.get('goals', {}).get('away', '—')}",
    ]
    if comparison:
        lines.append(
            f"- **Form comparison:** home {comparison.get('form', {}).get('home', '—')} "
            f"vs away {comparison.get('form', {}).get('away', '—')}"
        )
    return "\n".join(lines)


def _format_odds(
    fixture_id: int,
    *,
    team_a: str | None = None,
    team_b: str | None = None,
) -> str:
    odds_rows = api_football.get_odds(fixture_id)
    if not odds_rows:
        return "Odds not available from API-Football."

    def _label_value(value: str) -> str:
        if not team_a or not team_b:
            return value
        replacements = {"Home": team_a, "Away": team_b}
        for key, name in replacements.items():
            value = value.replace(key, name)
        return value

    market_rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    preferred_bookmakers = ("Bet365", "10Bet", "William Hill", "Marathonbet")

    for row in odds_rows:
        bookmakers = row.get("bookmakers") or []
        if not bookmakers and row.get("bookmaker"):
            bookmakers = [{"name": row["bookmaker"].get("name"), "bets": row.get("bets") or []}]

        bookmakers_sorted = sorted(
            bookmakers,
            key=lambda item: (
                preferred_bookmakers.index(item.get("name", ""))
                if item.get("name") in preferred_bookmakers
                else len(preferred_bookmakers)
            ),
        )

        for bookmaker in bookmakers_sorted:
            name = str(bookmaker.get("name") or "Bookmaker")
            for bet in bookmaker.get("bets") or []:
                label = str(bet.get("name", "")).strip()
                lowered = label.lower()
                if lowered not in {
                    "match winner",
                    "asian handicap",
                    "goals over/under",
                } and not any(
                    token in lowered for token in ("handicap", "over/under", "winner")
                ):
                    continue
                values = bet.get("values") or []
                if not values:
                    continue
                prices = " | ".join(
                    f"{_label_value(str(item.get('value', '')))} @ {item.get('odd')}"
                    for item in values[:6]
                )
                key = f"{name}:{label}"
                if key in seen:
                    continue
                seen.add(key)
                market_rows.append((label, name, prices))
                if len(market_rows) >= 9:
                    break
            if len(market_rows) >= 9:
                break
        if market_rows:
            break

    if not market_rows:
        return "Odds not available from API-Football."

    lines = [
        "| Market | Bookmaker | Prices |",
        "|---|---|---|",
    ]
    for label, bookmaker, prices in market_rows:
        lines.append(f"| {label} | {bookmaker} | {prices} |")
    return "\n".join(lines)


def _format_fixture_details(row: dict) -> str:
    home = api_football.team_name(row, home=True)
    away = api_football.team_name(row, home=False)
    fixture = row.get("fixture", {})
    referee = fixture.get("referee") or "TBD"
    venue = row.get("venue", {}) or {}
    venue_name = venue.get("name") or "TBD"
    city = venue.get("city") or ""
    status = fixture.get("status", {}).get("long", "Scheduled")
    round_name = row.get("league", {}).get("round", "")
    return "\n".join(
        [
            f"- **Match:** {home} vs {away}",
            f"- **Kickoff:** {fixture.get('date', 'TBD')}",
            f"- **Venue:** {venue_name}, {city}".rstrip(", "),
            f"- **Stage:** {round_name or api_football.stage_label(row)}",
            f"- **Status:** {status}",
            f"- **Referee:** {referee}",
        ]
    )


def _format_lineup_section(
    team_a_lineup: dict,
    team_b_lineup: dict,
    source: str,
) -> str:
    def describe(lineup: dict) -> list[str]:
        formation = lineup.get("formation", "?")
        starters = [
            entry.get("player", {}).get("name", "")
            for entry in lineup.get("startXI") or []
        ]
        bench = [
            entry.get("player", {}).get("name", "")
            for entry in lineup.get("substitutes") or []
        ]
        lines = [f"**Formation:** {formation}", ""]
        lines.append("**Starting XI:**")
        for index, name in enumerate(starters, start=1):
            lines.append(f"{index}. {name}")
        if bench:
            lines.append("")
            lines.append(f"**Bench:** {', '.join(bench[:7])}")
        return lines

    team_a_name = team_a_lineup.get("team", {}).get("name", "Team A")
    team_b_name = team_b_lineup.get("team", {}).get("name", "Team B")
    label = "Confirmed" if source == "official" else "Predicted"
    sections = [f"**Source:** API-Football ({label} lineups)", ""]
    sections.append(f"### {team_a_name}")
    sections.extend(describe(team_a_lineup))
    sections.append("")
    sections.append(f"### {team_b_name}")
    sections.extend(describe(team_b_lineup))
    return "\n".join(sections)


def gather_match_facts(match: Match, match_date: str) -> tuple[str, dict | None]:
    """Return markdown research (API facts) and formation block for the match."""
    if not match.fixture_id or not match.team_a_id or not match.team_b_id:
        raise ValueError(
            f"Match {match.team_a} vs {match.team_b} is missing API-Football IDs"
        )

    fixture_row = api_football.get_fixture(match.fixture_id)
    injuries = api_football.get_injuries(fixture_id=match.fixture_id)

    team_a_lineup, team_b_lineup, lineup_source = resolve_match_lineups(
        fixture_id=match.fixture_id,
        team_a_id=match.team_a_id,
        team_b_id=match.team_b_id,
        team_a_name=match.team_a,
        team_b_name=match.team_b,
    )

    unavailable_text = _format_injuries(injuries)
    formation_data = build_formation_block(
        team_a_name=match.team_a,
        team_b_name=match.team_b,
        team_a_lineup=team_a_lineup,
        team_b_lineup=team_b_lineup,
        unavailable=_injuries_summary(injuries),
        source=lineup_source,
    )

    sections: list[tuple[str, str]] = [
        (
            "Fixture Details (API-Football)",
            _format_fixture_details(fixture_row) if fixture_row else "Fixture details unavailable.",
        ),
        (
            "Standings & Match Context (API-Football)",
            _format_standings_context(match.team_a, match.team_b),
        ),
        (
            "Recent Form — Last 10 Games (API-Football)",
            "\n\n".join(
                [
                    _format_recent_form(match.team_a_id, match.team_a),
                    _format_recent_form(match.team_b_id, match.team_b),
                ]
            ),
        ),
        (
            "Lineups & Squads (API-Football)",
            "\n\n".join(
                [
                    _format_lineup_section(team_a_lineup, team_b_lineup, lineup_source),
                    _format_squads(match.team_a_id, match.team_b_id, match.team_a, match.team_b),
                ]
            ),
        ),
        (
            "Head-to-Head (API-Football)",
            _format_h2h(match.team_a_id, match.team_b_id, match.team_a, match.team_b),
        ),
        (
            "Player Form & Ratings (API-Football)",
            "\n\n".join(
                [
                    _format_player_form(match.team_a_id, match.team_a),
                    _format_player_form(match.team_b_id, match.team_b),
                ]
            ),
        ),
        (
            "Injuries & Unavailable (API-Football)",
            unavailable_text,
        ),
        (
            "Suspensions (API-Football)",
            "\n\n".join(
                [
                    _format_suspensions(
                        match.team_a_id,
                        match.team_a,
                        api_football.get_team_recent_fixtures(match.team_a_id, last=3),
                    ),
                    _format_suspensions(
                        match.team_b_id,
                        match.team_b,
                        api_football.get_team_recent_fixtures(match.team_b_id, last=3),
                    ),
                ]
            ),
        ),
        (
            "Predictions (API-Football)",
            _format_predictions(match.fixture_id),
        ),
        (
            "Betting Odds (API-Football)",
            _format_odds(match.fixture_id, team_a=match.team_a, team_b=match.team_b),
        ),
    ]

    body = "\n\n---\n\n".join(f"## {title}\n\n{content}" for title, content in sections)
    logger.info(
        "Gathered API-Football facts for %s vs %s (lineups: %s)",
        match.team_a,
        match.team_b,
        lineup_source,
    )
    return body, formation_data


def row_to_match(row: dict) -> Match:
    status = row.get("fixture", {}).get("status", {}).get("short", "")
    if status in {"CANC", "ABD", "AWD", "WO"}:
        raise ValueError("Fixture is cancelled or abandoned")
    kickoff = row.get("fixture", {}).get("date", "")
    return Match(
        team_a=api_football.team_name(row, home=True),
        team_b=api_football.team_name(row, home=False),
        fixture_id=api_football.fixture_id_from_row(row),
        team_a_id=api_football.team_id_from_row(row, home=True),
        team_b_id=api_football.team_id_from_row(row, home=False),
        report_date=kickoff[:10] if kickoff else None,
    )


def fixtures_to_matches(report_date: str) -> list[Match]:
    rows = api_football.get_fixtures_for_date(report_date)
    matches: list[Match] = []
    for row in rows:
        try:
            matches.append(row_to_match(row))
        except ValueError:
            continue
    return matches


def resolve_fixtures_by_ids(fixture_ids: list[int]) -> list[Match]:
    if not fixture_ids:
        return []
    rows = api_football.get_fixtures_by_ids(fixture_ids)
    by_id = {api_football.fixture_id_from_row(row): row for row in rows}
    matches: list[Match] = []
    for fixture_id in fixture_ids:
        row = by_id.get(fixture_id)
        if not row:
            continue
        try:
            matches.append(row_to_match(row))
        except ValueError:
            continue
    return matches


def _fixture_list_item(row: dict, existing_slugs: set[str]) -> dict:
    match = row_to_match(row)
    slug = match_slug(match.team_a, match.team_b)
    report_date = match.report_date or ""
    fixture = row.get("fixture", {})
    venue = row.get("venue", {}) or {}
    has_report = slug in existing_slugs
    item = {
        "fixture_id": match.fixture_id,
        "report_date": report_date,
        "team_a": match.team_a,
        "team_b": match.team_b,
        "kickoff": fixture.get("date"),
        "venue": venue.get("name") or "TBD",
        "city": venue.get("city") or "",
        "stage": row.get("league", {}).get("round") or api_football.stage_label(row),
        "status": fixture.get("status", {}).get("short", "NS"),
        "has_report": has_report,
        "pdf_slug": slug if has_report else None,
        "pdf_url": f"/reports/{report_date}/{slug}.pdf" if has_report else None,
    }
    return item


def list_upcoming_fixtures(*, days: int = 2) -> dict:
    from datetime import date, timedelta

    from services import reports_db

    today = date.today()
    day_list = [today + timedelta(days=offset) for offset in range(days)]
    fixtures: list[dict] = []
    dates: list[str] = []

    for day in day_list:
        report_date = day.isoformat()
        dates.append(report_date)
        existing_slugs = reports_db.get_existing_slugs(report_date)
        rows = api_football.get_fixtures_for_date(report_date)
        for row in rows:
            try:
                fixtures.append(_fixture_list_item(row, existing_slugs))
            except ValueError:
                continue

    fixtures.sort(key=lambda item: (item["report_date"], item.get("kickoff") or ""))
    return {"dates": dates, "fixtures": fixtures}
