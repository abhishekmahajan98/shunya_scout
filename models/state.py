from typing import List, TypedDict

from pydantic import BaseModel


class Match(BaseModel):
    team_a: str
    team_b: str
    fixture_id: int | None = None
    team_a_id: int | None = None
    team_b_id: int | None = None
    report_date: str | None = None


class MatchReport(BaseModel):
    match: Match
    raw_scout_data: str = ""
    final_analysis: str = ""
    pdf_slug: str = ""
    formation_data: dict | None = None


class GraphState(TypedDict):
    date: str
    matches: List[Match]
    reports: List[MatchReport]


def coerce_match(data: Match | dict) -> Match:
    if isinstance(data, Match):
        return data
    team_a = data.get("team_a") or data.get("teamA") or data.get("home") or ""
    team_b = data.get("team_b") or data.get("teamB") or data.get("away") or ""
    return Match(
        team_a=str(team_a).strip(),
        team_b=str(team_b).strip(),
        fixture_id=data.get("fixture_id"),
        team_a_id=data.get("team_a_id"),
        team_b_id=data.get("team_b_id"),
        report_date=data.get("report_date"),
    )


def coerce_report(data: MatchReport | dict) -> MatchReport:
    if isinstance(data, MatchReport):
        return data
    match = data.get("match", {})
    return MatchReport(
        match=coerce_match(match),
        raw_scout_data=data.get("raw_scout_data", ""),
        final_analysis=data.get("final_analysis", ""),
        pdf_slug=data.get("pdf_slug", ""),
        formation_data=data.get("formation_data"),
    )


def normalize_matches(raw_matches: list[dict]) -> list[Match]:
    matches: list[Match] = []
    for item in raw_matches:
        match = coerce_match(item)
        if match.team_a and match.team_b:
            matches.append(match)
    return matches
