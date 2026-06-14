import base64
import logging
import os
import re

import resend
from resend.emails._attachment import Attachment

from services import reports_db
from services.report_parse import extract_executive_summary, extract_verdict

logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _snippet(text: str, *, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _match_cards_html(report_date: str) -> str:
    reports = reports_db.get_markdown_reports_for_date(report_date)
    if not reports:
        return ""

    cards: list[str] = []
    for report in reports:
        team_a = report["team_a"]
        team_b = report["team_b"]
        summary = _snippet(extract_executive_summary(report["markdown"]))
        verdict = _snippet(extract_verdict(report["markdown"]), limit=160)

        cards.append(
            f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px;">
              <div style="font-size: 15px; font-weight: 600; color: #111827; margin-bottom: 4px;">
                {team_a} vs {team_b}
              </div>
              <div style="font-size: 13px; color: #374151; line-height: 1.5; margin-bottom: 6px;">{summary}</div>
              <div style="font-size: 12px; color: #059669; font-weight: 600;">{verdict}</div>
            </div>
            """
        )
    return "".join(cards)


def _build_html(report_date: str, match_count: int) -> str:
    cards = _match_cards_html(report_date)
    if not cards:
        return f"""
        <div style="font-family: sans-serif; color: #111827; max-width: 560px;">
          <h2 style="color: #059669; margin-bottom: 8px;">Shunya Scout</h2>
          <p>No match reports were generated for <strong>{report_date}</strong>.</p>
        </div>
        """

    files = "PDF" if match_count == 1 else "PDFs"
    return f"""
    <div style="font-family: sans-serif; color: #111827; max-width: 560px;">
      <h2 style="color: #059669; margin-bottom: 4px;">Shunya Scout</h2>
      <p style="color: #6b7280; font-size: 14px; margin-top: 0;">
        Morning match reports for <strong>{report_date}</strong> · {match_count} fixture{"s" if match_count != 1 else ""}
      </p>
      {cards}
      <p style="color: #6b7280; font-size: 13px; margin-top: 16px;">
        {match_count} match report {files} attached — one per fixture.
      </p>
    </div>
    """


def _match_attachments(report_date: str, entries: list[dict]) -> list[Attachment]:
    attachments: list[Attachment] = []
    for entry in entries:
        slug = entry["pdf_slug"]
        pdf_bytes = reports_db.download_pdf_bytes(report_date, slug)
        if not pdf_bytes:
            logger.warning("PDF missing in storage for %s on %s", slug, report_date)
            continue
        attachments.append(
            {
                "filename": f"{slug}-shunya-scout.pdf",
                "content": base64.b64encode(pdf_bytes).decode("utf-8"),
                "content_type": "application/pdf",
            }
        )
    return attachments


def _email_subject(report_date: str, match_count: int) -> str:
    reports = reports_db.get_markdown_reports_for_date(report_date)
    if len(reports) == 1:
        report = reports[0]
        return f"Shunya Scout — {report['team_a']} vs {report['team_b']} · {report_date}"
    return f"Shunya Scout — {match_count} morning reports · {report_date}"


def send_daily_report_email(
    report_date: str,
    entries: list[dict],
    *,
    to: str | None = None,
    from_addr: str | None = None,
) -> dict:
    resend.api_key = _require_env("RESEND_API_KEY")

    recipient = to or os.environ.get("EMAIL_TO", "abhishek.mahajan314@gmail.com")
    sender = from_addr or os.environ.get(
        "EMAIL_FROM", "Shunya Scout <onboarding@resend.dev>"
    )

    match_count = len(entries)
    attachments = _match_attachments(report_date, entries)

    if entries and not attachments:
        raise ValueError(
            f"Reports exist for {report_date} but no PDF files were found in storage"
        )

    subject = _email_subject(report_date, match_count) if entries else (
        f"Shunya Scout — no reports for {report_date}"
    )

    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": _build_html(report_date, match_count),
    }

    if attachments:
        params["attachments"] = attachments

    logger.info(
        "Sending email to %s with %d PDF attachment(s)",
        recipient,
        len(attachments),
    )
    result = resend.Emails.send(params)
    email_id = result.get("id", result)
    logger.info("Email sent: %s", email_id)
    return {"id": email_id, "attachment_count": len(attachments)}
