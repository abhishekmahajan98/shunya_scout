#!/usr/bin/env python3
"""Generate today's reports and email them via Resend."""

import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# Allow imports from project root when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from run_graph import load_report_entries, run_pipeline  # noqa: E402
from services.email import send_daily_report_email  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    report_date = date.today().isoformat()
    logger.info("Starting daily job for %s", report_date)

    result = run_pipeline(report_date)
    entries = load_report_entries(report_date)
    match_count = len(result.get("matches", []))
    report_count = len(entries)

    logger.info(
        "Pipeline finished: %d matches, %d reports",
        match_count,
        report_count,
    )

    send_daily_report_email(report_date, entries)
    logger.info("Daily job complete")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Daily job failed")
        sys.exit(1)
