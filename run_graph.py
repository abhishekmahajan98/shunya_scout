import json
import logging
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from graph.workflow import build_graph
from models.state import GraphState, MatchReport, coerce_report
from services.pdf import generate_match_pdf
from services.quick_report import build_sample_markdown
from utils.slug import match_slug

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REPORTS_DIR = Path("data/reports")


def load_report_entries(report_date: str) -> list[dict]:
    index_path = REPORTS_DIR / f"{report_date}.json"
    if not index_path.exists():
        return []
    return json.loads(index_path.read_text()).get("reports", [])


def _save_reports(report_date: str, reports: list[MatchReport | dict]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_dir = REPORTS_DIR / report_date
    output_path = REPORTS_DIR / f"{report_date}.json"

    saved: list[dict] = []
    for item in reports:
        report = coerce_report(item)
        slug = match_slug(report.match.team_a, report.match.team_b)
        if report.final_analysis:
            generate_match_pdf(
                report.final_analysis,
                report.match.team_a,
                report.match.team_b,
                report_date,
                pdf_dir,
            )
        saved.append(
            {
                "match": report.match.model_dump(),
                "pdf_slug": slug,
                "pdf_url": f"/reports/{report_date}/{slug}.pdf",
            }
        )

    payload = {"date": report_date, "reports": saved}
    output_path.write_text(json.dumps(payload, indent=2))
    logger.info("Saved %d reports to %s", len(saved), output_path)
    return output_path


def _merge_index_entry(report_date: str, entry: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"{report_date}.json"
    slug = entry["pdf_slug"]

    if output_path.exists():
        payload = json.loads(output_path.read_text())
        reports = [r for r in payload.get("reports", []) if r.get("pdf_slug") != slug]
    else:
        reports = []

    reports.append(entry)
    payload = {"date": report_date, "reports": reports}
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def run_quick_report(
    team_a: str = "Argentina",
    team_b: str = "France",
    target_date: str | None = None,
) -> dict:
    report_date = target_date or date.today().isoformat()
    markdown = build_sample_markdown(team_a, team_b, report_date)
    slug = match_slug(team_a, team_b)
    pdf_dir = REPORTS_DIR / report_date

    generate_match_pdf(markdown, team_a, team_b, report_date, pdf_dir)
    entry = {
        "match": {"team_a": team_a, "team_b": team_b},
        "pdf_slug": slug,
        "pdf_url": f"/reports/{report_date}/{slug}.pdf",
        "quick_test": True,
    }
    _merge_index_entry(report_date, entry)
    logger.info("Quick test PDF generated for %s vs %s", team_a, team_b)
    return {"date": report_date, "downloads": [entry]}


def run_pipeline(target_date: str | None = None) -> GraphState:
    report_date = target_date or date.today().isoformat()
    initial_state: GraphState = {
        "date": report_date,
        "matches": [],
        "reports": [],
    }

    logger.info("Starting pipeline for %s", report_date)
    graph = build_graph()
    result = graph.invoke(initial_state)
    result["date"] = report_date

    reports = result.get("reports", [])
    if reports:
        _save_reports(report_date, reports)
    else:
        logger.info("No reports generated for %s", report_date)

    return result


if __name__ == "__main__":
    import sys

    if "--quick" in sys.argv:
        result = run_quick_report()
        entry = result["downloads"][0]
        print(f"Quick test PDF ready: {entry['pdf_url']}")
    else:
        final_state = run_pipeline()
        match_count = len(final_state.get("matches", []))
        report_count = len(final_state.get("reports", []))
        print(f"Pipeline complete: {match_count} matches, {report_count} reports generated.")
