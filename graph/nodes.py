import logging

from models.state import GraphState, Match, MatchReport, coerce_report
from services.gemini import analyze_match
from services.match_facts import fixtures_to_matches
from services.scout_research import research_match

logger = logging.getLogger(__name__)


def scheduler_node(state: GraphState) -> dict:
    current_date = state["date"]
    matches = fixtures_to_matches(current_date)
    logger.info("Scheduler found %d matches for %s", len(matches), current_date)
    return {"matches": matches}


def _scout_match(match: Match, default_date: str) -> MatchReport:
    match_date = match.report_date or default_date
    logger.info("Scouting %s vs %s", match.team_a, match.team_b)
    raw_scout_data, formation_data = research_match(match, match_date)
    return MatchReport(
        match=match,
        raw_scout_data=raw_scout_data,
        final_analysis="",
        formation_data=formation_data,
    )


def scout_node(state: GraphState) -> dict:
    match_date = state["date"]
    reports = [_scout_match(match, match_date) for match in state["matches"]]
    return {"reports": reports}


def _analyze_report(item: MatchReport | dict, default_date: str) -> MatchReport:
    report = coerce_report(item)
    match_date = report.match.report_date or default_date
    logger.info("Analyzing %s vs %s", report.match.team_a, report.match.team_b)
    final_analysis = analyze_match(
        report.match.team_a,
        report.match.team_b,
        report.raw_scout_data,
        match_date,
        formation_data=report.formation_data,
    )
    return MatchReport(
        match=report.match,
        raw_scout_data=report.raw_scout_data,
        final_analysis=final_analysis,
        formation_data=report.formation_data,
    )


def analyst_node(state: GraphState) -> dict:
    match_date = state["date"]
    reports = [_analyze_report(item, match_date) for item in state["reports"]]
    return {"reports": reports}
