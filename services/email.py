import base64
import logging
import os
from pathlib import Path

import resend
from resend.emails._attachment import Attachment

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is not set")
    return value


def _build_html(report_date: str, entries: list[dict], attachment_count: int) -> str:
    if not entries:
        return f"""
        <div style="font-family: sans-serif; color: #111827; max-width: 560px;">
          <h2 style="color: #059669; margin-bottom: 8px;">Shunya Scout</h2>
          <p>No match reports were generated for <strong>{report_date}</strong>.</p>
          <p style="color: #6b7280; font-size: 14px;">The pipeline ran successfully but found no fixtures for today.</p>
        </div>
        """

    items = "".join(
        f"<li><strong>{entry['match']['team_a']}</strong> vs "
        f"<strong>{entry['match']['team_b']}</strong></li>"
        for entry in entries
    )
    return f"""
    <div style="font-family: sans-serif; color: #111827; max-width: 560px;">
      <h2 style="color: #059669; margin-bottom: 8px;">Shunya Scout</h2>
      <p>Your daily match reports for <strong>{report_date}</strong> are ready.</p>
      <ul>{items}</ul>
      <p style="color: #6b7280; font-size: 14px;">
        {attachment_count} PDF{"s" if attachment_count != 1 else ""} attached to this email.
      </p>
    </div>
    """


def _pdf_files_for_date(report_date: str, entries: list[dict]) -> list[tuple[str, Path]]:
    pdf_dir = REPORTS_DIR / report_date
    seen: set[str] = set()
    files: list[tuple[str, Path]] = []

    for entry in entries:
        slug = entry["pdf_slug"]
        pdf_path = pdf_dir / f"{slug}.pdf"
        filename = f"{slug}-shunya-scout.pdf"
        if pdf_path.exists() and filename not in seen:
            files.append((filename, pdf_path))
            seen.add(filename)
        elif not pdf_path.exists():
            logger.warning("PDF missing for %s at %s", slug, pdf_path)

    if pdf_dir.exists():
        for pdf_path in sorted(pdf_dir.glob("*.pdf")):
            filename = f"{pdf_path.stem}-shunya-scout.pdf"
            if filename not in seen:
                files.append((filename, pdf_path))
                seen.add(filename)

    return files


def _pdf_attachments(report_date: str, entries: list[dict]) -> list[Attachment]:
    attachments: list[Attachment] = []
    for filename, pdf_path in _pdf_files_for_date(report_date, entries):
        attachments.append(
            {
                "filename": filename,
                "content": base64.b64encode(pdf_path.read_bytes()).decode("utf-8"),
                "content_type": "application/pdf",
            }
        )
    return attachments


def send_daily_report_email(
    report_date: str,
    entries: list[dict],
    *,
    to: str | None = None,
    from_addr: str | None = None,
    quick_test: bool = False,
) -> dict:
    resend.api_key = _require_env("RESEND_API_KEY")

    recipient = to or os.environ.get("EMAIL_TO", "abhishek.mahajan314@gmail.com")
    sender = from_addr or os.environ.get(
        "EMAIL_FROM", "Shunya Scout <onboarding@resend.dev>"
    )

    attachments = _pdf_attachments(report_date, entries)
    if entries and not attachments:
        raise ValueError(
            f"Reports were generated for {report_date} but no PDF files were found to attach"
        )

    prefix = "Shunya Scout [Quick Test]" if quick_test else "Shunya Scout"
    count = len(entries)
    if count:
        subject = (
            f"{prefix} — {count} report{'s' if count != 1 else ''} for {report_date}"
        )
    else:
        subject = f"{prefix} — no reports for {report_date}"

    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": _build_html(report_date, entries, len(attachments)),
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
