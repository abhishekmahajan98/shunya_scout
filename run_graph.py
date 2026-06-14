import logging
from datetime import date

from dotenv import load_dotenv

from graph.nodes import analyst_node, scout_node
from models.state import GraphState, Match, MatchReport, coerce_report
from services import reports_db
from services.match_facts import resolve_fixtures_by_ids
from utils.dates import require_mutable_report_date
from utils.limits import estimate_api_calls, max_api_concurrency
from utils.slug import match_slug

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_report_entries(report_date: str) -> list[dict]:
    return reports_db.get_reports_for_date(report_date)


def _generate_reports(matches: list[Match]) -> list[MatchReport]:
    if not matches:
        return []

    primary_date = matches[0].report_date or date.today().isoformat()
    budget = estimate_api_calls(len(matches))
    logger.info(
        "Generating %d report(s). "
        "API budget (max): %d API-Football, %d Perplexity, %d Gemini. "
        "Parallel concurrency: %d",
        len(matches),
        budget["api_football_max"],
        budget["perplexity_max"],
        budget["gemini_max"],
        max_api_concurrency(),
    )
    run_state: GraphState = {
        "date": primary_date,
        "matches": matches,
        "reports": [],
    }
    run_state.update(scout_node(run_state))
    run_state.update(analyst_node(run_state))
    return [coerce_report(item) for item in run_state["reports"]]


def _save_reports(reports: list[MatchReport], *, fallback_date: str) -> None:
    for report in reports:
        save_date = report.match.report_date or fallback_date
        reports_db.save_report(save_date, report)


def run_pipeline(
    fixture_ids: list[int],
    *,
    skip_existing: bool = False,
) -> dict:
    if not fixture_ids:
        raise ValueError("At least one fixture_id is required")

    all_matches = resolve_fixtures_by_ids(fixture_ids)
    if not all_matches:
        raise ValueError("No valid fixtures found for the selected IDs")

    found_ids = {match.fixture_id for match in all_matches}
    missing = [fixture_id for fixture_id in fixture_ids if fixture_id not in found_ids]
    if missing:
        raise ValueError(f"Fixture IDs not found: {', '.join(str(i) for i in missing)}")

    for match in all_matches:
        if not match.report_date:
            raise ValueError(f"Fixture {match.fixture_id} is missing a report date")
        require_mutable_report_date(match.report_date)

    if not skip_existing:
        for match in all_matches:
            reports_db.delete_report(
                match.report_date,
                match_slug(match.team_a, match.team_b),
            )

    matches_to_run = all_matches
    if skip_existing:
        matches_to_run = [
            match
            for match in all_matches
            if match_slug(match.team_a, match.team_b)
            not in reports_db.get_existing_slugs(match.report_date)
        ]

    skipped_count = len(all_matches) - len(matches_to_run)
    generated_reports = _generate_reports(matches_to_run)
    fallback_date = all_matches[0].report_date or date.today().isoformat()
    _save_reports(generated_reports, fallback_date=fallback_date)

    affected_dates = sorted({match.report_date for match in all_matches if match.report_date})
    return {
        "date": affected_dates[0] if len(affected_dates) == 1 else None,
        "dates": affected_dates,
        "matches": all_matches,
        "reports": generated_reports,
        "skipped_count": skipped_count,
        "generated_count": len(generated_reports),
        "fixture_ids": fixture_ids,
    }
