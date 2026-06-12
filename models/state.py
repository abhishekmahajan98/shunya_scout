from typing import List, TypedDict

from pydantic import BaseModel


class Match(BaseModel):
    team_a: str
    team_b: str


class MatchReport(BaseModel):
    match: Match
    raw_scout_data: str = ""
    final_analysis: str = ""
    pdf_slug: str = ""


class GraphState(TypedDict):
    date: str
    matches: List[Match]
    reports: List[MatchReport]


def coerce_match(data: Match | dict) -> Match:
    if isinstance(data, Match):
        return data
    team_a = data.get("team_a") or data.get("teamA") or data.get("home") or ""
    team_b = data.get("team_b") or data.get("teamB") or data.get("away") or ""
    return Match(team_a=str(team_a).strip(), team_b=str(team_b).strip())


def coerce_report(data: MatchReport | dict) -> MatchReport:
    if isinstance(data, MatchReport):
        return data
    match = data.get("match", {})
    return MatchReport(
        match=coerce_match(match),
        raw_scout_data=data.get("raw_scout_data", ""),
        final_analysis=data.get("final_analysis", ""),
        pdf_slug=data.get("pdf_slug", ""),
    )


def normalize_matches(raw_matches: list[dict]) -> list[Match]:
    matches: list[Match] = []
    for item in raw_matches:
        match = coerce_match(item)
        if match.team_a and match.team_b:
            matches.append(match)
    return matches
