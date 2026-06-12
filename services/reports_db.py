import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from supabase import Client, create_client

from models.state import MatchReport, coerce_report
from services.pdf import generate_match_pdf
from utils.slug import match_slug

logger = logging.getLogger(__name__)

TABLE = "match_reports"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


@lru_cache
def get_client() -> Client:
    # Publishable (anon) key — used only on the server; all client traffic goes through the API.
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not key:
        key = _require_env("SUPABASE_ANON_KEY")
    return create_client(_require_env("SUPABASE_URL"), key)


def storage_bucket() -> str:
    return os.environ.get("SUPABASE_STORAGE_BUCKET", "reports")


def storage_path_for(report_date: str, pdf_slug: str) -> str:
    return f"{report_date}/{pdf_slug}.pdf"


def row_to_entry(row: dict) -> dict:
    report_date = row["report_date"]
    pdf_slug = row["pdf_slug"]
    return {
        "match": {"team_a": row["team_a"], "team_b": row["team_b"]},
        "pdf_slug": pdf_slug,
        "pdf_url": f"/reports/{report_date}/{pdf_slug}.pdf",
        "quick_test": bool(row.get("quick_test")),
        "created_at": row.get("created_at"),
    }


def list_report_dates() -> list[str]:
    client = get_client()
    rows = (
        client.table(TABLE)
        .select("report_date")
        .order("report_date", desc=True)
        .execute()
        .data
        or []
    )
    seen: set[str] = set()
    dates: list[str] = []
    for row in rows:
        value = row["report_date"]
        if value not in seen:
            seen.add(value)
            dates.append(value)
    return dates


def get_reports_for_date(report_date: str) -> list[dict]:
    client = get_client()
    rows = (
        client.table(TABLE)
        .select("*")
        .eq("report_date", report_date)
        .order("team_a")
        .execute()
        .data
        or []
    )
    return [row_to_entry(row) for row in rows]


def get_existing_slugs(report_date: str, *, exclude_quick_test: bool = True) -> set[str]:
    client = get_client()
    query = client.table(TABLE).select("pdf_slug, quick_test").eq("report_date", report_date)
    rows = query.execute().data or []
    return {
        row["pdf_slug"]
        for row in rows
        if not exclude_quick_test or not row.get("quick_test")
    }


def download_pdf_bytes(report_date: str, pdf_slug: str) -> bytes | None:
    client = get_client()
    path = storage_path_for(report_date, pdf_slug)
    try:
        return client.storage.from_(storage_bucket()).download(path)
    except Exception:
        logger.exception("Failed to download %s from storage", path)
        return None


def save_report(
    report_date: str,
    report: MatchReport | dict,
    *,
    quick_test: bool = False,
) -> dict:
    item = coerce_report(report)
    slug = match_slug(item.match.team_a, item.match.team_b)
    markdown = item.final_analysis
    if not markdown:
        raise ValueError(f"No report content for {item.match.team_a} vs {item.match.team_b}")

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = generate_match_pdf(
            markdown,
            item.match.team_a,
            item.match.team_b,
            report_date,
            Path(tmp),
        )
        pdf_bytes = pdf_path.read_bytes()

    storage_path = storage_path_for(report_date, slug)
    client = get_client()
    bucket = storage_bucket()
    client.storage.from_(bucket).upload(
        storage_path,
        pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )

    payload = {
        "report_date": report_date,
        "team_a": item.match.team_a,
        "team_b": item.match.team_b,
        "pdf_slug": slug,
        "markdown": markdown,
        "raw_scout_data": item.raw_scout_data,
        "storage_path": storage_path,
        "quick_test": quick_test,
    }
    client.table(TABLE).upsert(payload, on_conflict="report_date,pdf_slug").execute()
    logger.info("Saved report to Supabase: %s", storage_path)
    return row_to_entry({**payload, "created_at": None})
