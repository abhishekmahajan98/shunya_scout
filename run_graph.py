import logging
from datetime import date

from dotenv import load_dotenv

from graph.nodes import analyst_node, scheduler_node, scout_node
from models.state import GraphState, MatchReport, coerce_report
from services import reports_db
from utils.dates import require_mutable_report_date
from utils.limits import estimate_api_calls, max_matches_per_run
from utils.slug import match_slug

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_report_entries(report_date: str) -> list[dict]:
    return reports_db.get_reports_for_date(report_date)


def run_pipeline(
    target_date: str | None = None,
    *,
    skip_existing: bool = False,
) -> dict:
    report_date = target_date or date.today().isoformat()
    if not skip_existing:
        require_mutable_report_date(report_date)
        reports_db.clear_reports_for_date(report_date)

    state: GraphState = {"date": report_date, "matches": [], "reports": []}
    state.update(scheduler_node(state))
    all_matches = state["matches"]

    cap = max_matches_per_run()
    if len(all_matches) > cap:
        logger.warning(
            "Scheduler returned %d matches for %s; capping at %d (set MAX_MATCHES_PER_RUN)",
            len(all_matches),
            report_date,
            cap,
        )
        all_matches = all_matches[:cap]

    existing_slugs = reports_db.get_existing_slugs(report_date)

    if skip_existing:
        matches_to_run = [
            match
            for match in all_matches
            if match_slug(match.team_a, match.team_b) not in existing_slugs
        ]
    else:
        matches_to_run = all_matches

    skipped_count = len(all_matches) - len(matches_to_run)
    generated_reports: list[MatchReport] = []

    if matches_to_run:
        budget = estimate_api_calls(len(matches_to_run))
        logger.info(
            "Generating %d report(s) for %s (%d skipped). "
            "API budget (max): %d Perplexity + %d Gemini",
            len(matches_to_run),
            report_date,
            skipped_count,
            budget["perplexity_max"],
            budget["gemini_max"],
        )
        run_state: GraphState = {
            "date": report_date,
            "matches": matches_to_run,
            "reports": [],
        }
        run_state.update(scout_node(run_state))
        run_state.update(analyst_node(run_state))
        generated_reports = [coerce_report(item) for item in run_state["reports"]]
        for report in generated_reports:
            reports_db.save_report(report_date, report)
    else:
        logger.info(
            "No new reports needed for %s (%d existing)",
            report_date,
            skipped_count,
        )

    return {
        "date": report_date,
        "matches": all_matches,
        "reports": generated_reports,
        "skipped_count": skipped_count,
        "generated_count": len(generated_reports),
    }


if __name__ == "__main__":
    final_state = run_pipeline(skip_existing=True)
    print(
        "Pipeline complete: "
        f"{len(final_state.get('matches', []))} matches, "
        f"{final_state.get('generated_count', 0)} generated, "
        f"{final_state.get('skipped_count', 0)} skipped."
    )
