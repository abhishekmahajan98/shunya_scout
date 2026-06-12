import logging
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from dependencies.auth import require_user
from run_graph import load_report_entries, run_pipeline, run_quick_report
from services import reports_db
from services.auth import AuthError, refresh_session, sign_in, sign_out, sign_up
from services.email import send_daily_report_email
from services.frontend_static import frontend_dist_exists, mount_frontend
from utils.dates import parse_report_date, require_mutable_report_date
from utils.slug import match_slug

logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Shunya Scout",
    description="Daily multi-agent pipeline for FIFA World Cup match reports",
    version="1.0.0",
    docs_url=None if frontend_dist_exists() else "/docs",
    redoc_url=None if frontend_dist_exists() else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    date: str | None = None


class QuickReportRequest(BaseModel):
    date: str | None = None
    team_a: str = "Argentina"
    team_b: str = "France"


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


def _download_entry(report_date: str, entry: dict) -> dict:
    match = entry["match"]
    slug = entry.get("pdf_slug") or match_slug(match["team_a"], match["team_b"])
    return {
        "match": match,
        "pdf_slug": slug,
        "pdf_url": f"/reports/{report_date}/{slug}.pdf",
        "quick_test": entry.get("quick_test", False),
        "created_at": entry.get("created_at"),
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


def _pipeline_response(result: dict, entries: list[dict], *, email: dict) -> dict:
    downloads = [_download_entry(result["date"], entry) for entry in entries]
    return {
        "date": result["date"],
        "match_count": len(result.get("matches", [])),
        "report_count": len(downloads),
        "generated_count": result.get("generated_count", 0),
        "skipped_count": result.get("skipped_count", 0),
        "downloads": downloads,
        **email,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/signup")
def signup(body: AuthRequest):
    try:
        session = sign_up(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not session.get("access_token"):
        return {
            "message": "Check your email to confirm your account.",
            "user": session["user"],
        }
    return session


@app.post("/auth/login")
def login(body: AuthRequest):
    try:
        return sign_in(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.post("/auth/refresh")
def refresh(body: RefreshRequest):
    try:
        return refresh_session(body.refresh_token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@app.get("/auth/me")
def me(user: dict = Depends(require_user)):
    return {"user": user}


@app.post("/auth/logout")
def logout(
    user: dict = Depends(require_user),
    authorization: str | None = Header(default=None),
):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            sign_out(token)
        except AuthError:
            pass
    return {"ok": True}


@app.post("/run")
def trigger_pipeline(
    body: RunRequest | None = None,
    user: dict = Depends(require_user),
):
    target_date = body.date if body else None
    if target_date:
        try:
            require_mutable_report_date(target_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = run_pipeline(target_date, skip_existing=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    report_date = result["date"]
    entries = load_report_entries(report_date)
    email = _send_report_email(report_date, entries)
    return _pipeline_response(result, entries, email=email)


@app.post("/run/regenerate")
def regenerate_pipeline(
    body: RunRequest,
    user: dict = Depends(require_user),
):
    if not body.date:
        raise HTTPException(status_code=400, detail="date is required")
    try:
        require_mutable_report_date(body.date)
        result = run_pipeline(body.date, regenerate=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    report_date = result["date"]
    entries = load_report_entries(report_date)
    email = _send_report_email(report_date, entries)
    return _pipeline_response(result, entries, email=email)


@app.post("/run/quick")
def trigger_quick_report(
    body: QuickReportRequest | None = None,
    user: dict = Depends(require_user),
):
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
        "generated_count": 1,
        "skipped_count": 0,
        "quick_test": True,
        "downloads": entries,
        **email,
    }


@app.get("/reports")
def list_report_dates(user: dict = Depends(require_user)):
    return {"dates": reports_db.list_report_dates()}


@app.get("/reports/today/latest")
def get_today_downloads(user: dict = Depends(require_user)):
    today = date.today().isoformat()
    entries = load_report_entries(today)
    return {
        "date": today,
        "downloads": [_download_entry(today, entry) for entry in entries],
    }


@app.get("/reports/{report_date}")
def get_report_index(report_date: str, user: dict = Depends(require_user)):
    try:
        parse_report_date(report_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entries = load_report_entries(report_date)
    return {
        "date": report_date,
        "downloads": [_download_entry(report_date, entry) for entry in entries],
    }


@app.get("/reports/{report_date}/{pdf_slug}.pdf")
def download_report_pdf(
    report_date: str,
    pdf_slug: str,
    user: dict = Depends(require_user),
):
    pdf_bytes = reports_db.download_pdf_bytes(report_date, pdf_slug)
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF not found")
    filename = f"{pdf_slug}-shunya-scout.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


mount_frontend(app)
