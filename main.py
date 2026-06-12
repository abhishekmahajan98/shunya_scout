import json
import logging
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from run_graph import load_report_entries, run_pipeline, run_quick_report
from services.email import send_daily_report_email
from utils.slug import match_slug

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Shunya Scout",
    description="Daily multi-agent pipeline for FIFA World Cup match reports",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = Path("data/reports")


class RunRequest(BaseModel):
    date: str | None = None


class QuickReportRequest(BaseModel):
    date: str | None = None
    team_a: str = "Argentina"
    team_b: str = "France"


def _load_index(report_date: str) -> dict:
    report_path = REPORTS_DIR / f"{report_date}.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"No report for {report_date}")
    return json.loads(report_path.read_text())


def _download_entry(report_date: str, entry: dict) -> dict:
    match = entry["match"]
    slug = entry.get("pdf_slug") or match_slug(match["team_a"], match["team_b"])
    return {
        "match": match,
        "pdf_slug": slug,
        "pdf_url": f"/reports/{report_date}/{slug}.pdf",
    }


def _send_report_email(
    report_date: str,
    entries: list[dict],
    *,
    quick_test: bool = False,
) -> dict:
    email_sent = False
    email_to = os.environ.get("EMAIL_TO", "abhishek.mahajan314@gmail.com")
    email_error: str | None = None
    attachment_count = 0
    try:
        email_result = send_daily_report_email(
            report_date, entries, quick_test=quick_test
        )
        email_sent = True
        attachment_count = email_result.get("attachment_count", 0)
    except Exception as exc:
        email_error = str(exc)
        logger.exception("Failed to send report email for %s", report_date)
    return {
        "email_sent": email_sent,
        "email_to": email_to if email_sent else None,
        "email_error": email_error,
        "attachment_count": attachment_count,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def trigger_pipeline(body: RunRequest | None = None):
    target_date = body.date if body else None
    try:
        result = run_pipeline(target_date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    report_date = result.get("date") or (
        body.date if body and body.date else date.today().isoformat()
    )
    entries = load_report_entries(report_date)
    downloads = [_download_entry(report_date, r) for r in entries]

    email = _send_report_email(report_date, entries)

    return {
        "date": report_date,
        "match_count": len(result.get("matches", [])),
        "report_count": len(downloads),
        "downloads": downloads,
        **email,
    }


@app.post("/run/quick")
def trigger_quick_report(body: QuickReportRequest | None = None):
    req = body or QuickReportRequest()
    try:
        result = run_quick_report(req.team_a, req.team_b, req.date)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    report_date = result["date"]
    entries = result["downloads"]
    email = _send_report_email(report_date, entries, quick_test=True)

    return {
        "date": report_date,
        "match_count": 1,
        "report_count": 1,
        "quick_test": True,
        "downloads": entries,
        **email,
    }


@app.get("/reports")
def list_report_dates():
    if not REPORTS_DIR.exists():
        return {"dates": []}
    dates = sorted(
        (p.stem for p in REPORTS_DIR.glob("*.json")),
        reverse=True,
    )
    return {"dates": dates}


@app.get("/reports/today/latest")
def get_today_downloads():
    today = date.today().isoformat()
    index = _load_index(today)
    return {
        "date": today,
        "downloads": [_download_entry(today, r) for r in index["reports"]],
    }


@app.get("/reports/{report_date}")
def get_report_index(report_date: str):
    index = _load_index(report_date)
    return {
        "date": report_date,
        "downloads": [_download_entry(report_date, r) for r in index["reports"]],
    }


@app.get("/reports/{report_date}/{pdf_slug}.pdf")
def download_report_pdf(report_date: str, pdf_slug: str):
    pdf_path = REPORTS_DIR / report_date / f"{pdf_slug}.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    filename = f"{pdf_slug}-shunya-scout.pdf"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename,
    )
