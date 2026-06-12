import logging

from models.state import GraphState, MatchReport, coerce_report, normalize_matches
from services.gemini import analyze_match
from services.perplexity import query_perplexity_json
from services.scout_research import research_match

logger = logging.getLogger(__name__)

SCHEDULER_SYSTEM = (
    "You are a precise data retrieval assistant. Return only a strict JSON "
    "array of objects representing today's FIFA World Cup matches. Do not "
    "include markdown formatting or conversational text."
)


def scheduler_node(state: GraphState) -> dict:
    current_date = state["date"]
    user_prompt = (
        f"Search the web for the official FIFA World Cup 2026 matches "
        f"scheduled for {current_date}. Return the matchups as a JSON "
        "array with 'team_a' and 'team_b' keys."
    )
    raw_matches = query_perplexity_json(SCHEDULER_SYSTEM, user_prompt)
    matches = normalize_matches(raw_matches)
    logger.info("Scheduler found %d matches for %s", len(matches), current_date)
    return {"matches": matches}


def scout_node(state: GraphState) -> dict:
    match_date = state["date"]
    reports: list[MatchReport] = []

    for match in state["matches"]:
        logger.info("Scouting %s vs %s", match.team_a, match.team_b)
        raw_scout_data = research_match(match.team_a, match.team_b, match_date)
        reports.append(
            MatchReport(
                match=match,
                raw_scout_data=raw_scout_data,
                final_analysis="",
            )
        )

    return {"reports": reports}


def analyst_node(state: GraphState) -> dict:
    match_date = state["date"]
    reports: list[MatchReport] = []

    for item in state["reports"]:
        report = coerce_report(item)
        logger.info("Analyzing %s vs %s", report.match.team_a, report.match.team_b)
        final_analysis = analyze_match(
            report.match.team_a,
            report.match.team_b,
            report.raw_scout_data,
            match_date,
        )
        reports.append(
            MatchReport(
                match=report.match,
                raw_scout_data=report.raw_scout_data,
                final_analysis=final_analysis,
            )
        )

    return {"reports": reports}
