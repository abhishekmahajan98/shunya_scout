import base64
import logging
import os

import resend
from resend.emails._attachment import Attachment

from services import reports_db
from services.report_parse import dashboard_field, extract_dashboard_block

logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _match_cards_html(report_date: str) -> str:
    reports = reports_db.get_markdown_reports_for_date(report_date)
    if not reports:
        return ""

    cards: list[str] = []
    for report in reports:
        _, dashboard = extract_dashboard_block(report["markdown"])
        team_a = report["team_a"]
        team_b = report["team_b"]
        score = dashboard_field(dashboard, "predicted_score")
        confidence = dashboard_field(dashboard, "confidence")
        best_bet = dashboard_field(dashboard, "best_bet")
        story = dashboard_field(dashboard, "tactical_story", default="")
        kickoff = dashboard_field(dashboard, "kickoff", default="")

        meta_parts = [part for part in (kickoff, f"{confidence} confidence") if part != "—"]
        meta = " · ".join(meta_parts)

        cards.append(
            f"""
            <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px;">
              <div style="font-size: 15px; font-weight: 600; color: #111827; margin-bottom: 4px;">
                {team_a} vs {team_b}
              </div>
              <div style="font-size: 13px; color: #059669; font-weight: 600; margin-bottom: 6px;">
                Pick {score} · {best_bet}
              </div>
              <div style="font-size: 12px; color: #6b7280; margin-bottom: 6px;">{meta}</div>
              <div style="font-size: 13px; color: #374151; line-height: 1.5;">{story}</div>
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

    return f"""
    <div style="font-family: sans-serif; color: #111827; max-width: 560px;">
      <h2 style="color: #059669; margin-bottom: 4px;">Shunya Scout</h2>
      <p style="color: #6b7280; font-size: 14px; margin-top: 0;">
        Matchday digest for <strong>{report_date}</strong> · {match_count} fixture{"s" if match_count != 1 else ""}
      </p>
      {cards}
      <p style="color: #6b7280; font-size: 13px; margin-top: 16px;">
        Full matchday digest PDF attached. Individual match reports are in the app.
      </p>
    </div>
    """


def _digest_attachment(report_date: str) -> Attachment | None:
    pdf_bytes = reports_db.download_digest_bytes(report_date)
    if not pdf_bytes:
        return None
    return {
        "filename": f"shunya-scout-matchday-{report_date}.pdf",
        "content": base64.b64encode(pdf_bytes).decode("utf-8"),
        "content_type": "application/pdf",
    }


def _fallback_attachments(report_date: str, entries: list[dict]) -> list[Attachment]:
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
        _, dashboard = extract_dashboard_block(report["markdown"])
        score = dashboard_field(dashboard, "predicted_score", default="")
        pick = f" — {score}" if score != "—" else ""
        return f"Shunya Scout — {report['team_a']} vs {report['team_b']}{pick}"
    return f"Shunya Scout — Matchday digest ({match_count} fixtures) · {report_date}"


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
    digest = _digest_attachment(report_date)
    attachments: list[Attachment] = [digest] if digest else _fallback_attachments(report_date, entries)

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
