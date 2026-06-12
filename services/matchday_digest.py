import logging
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from services.pdf_dashboard import write_dashboard_panel
from services.pdf_styles import ACCENT, BORDER, FONT, INK, INK_LIGHT, INK_MUTED
from services.report_parse import (
    extract_dashboard_block,
    extract_executive_summary,
    extract_game_state_scenarios,
    extract_verdict,
)

logger = logging.getLogger(__name__)

DIGEST_FILENAME = "matchday-digest.pdf"


class DigestPDF(FPDF):
    def __init__(self, report_date: str) -> None:
        super().__init__()
        self.report_date = report_date
        font_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
        self.add_font(FONT, "", str(font_dir / "NotoSans-Regular.ttf"))
        self.add_font(FONT, "B", str(font_dir / "NotoSans-Bold.ttf"))
        self.add_font(FONT, "I", str(font_dir / "NotoSans-Italic.ttf"))
        self.set_font(FONT, size=10)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font(FONT, "", 7.5)
        self.set_text_color(*INK_LIGHT)
        self.cell(0, 5, "FIFA World Cup 2026  |  Shunya Scout Matchday Digest", align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def _write_digest_cover(pdf: DigestPDF, report_date: str, match_count: int) -> None:
    generated_at = datetime.now().strftime("%B %d, %Y at %H:%M UTC")
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 3.5, style="F")
    pdf.set_y(20)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 7.5)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 4, "FIFA WORLD CUP 2026  /  SHUNYA SCOUT", ln=True)
    pdf.ln(4)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, "Matchday Digest", ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "", 11)
    pdf.set_text_color(*INK_MUTED)
    pdf.cell(0, 6, report_date, ln=True)
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "", 9)
    pdf.set_text_color(*INK_LIGHT)
    pdf.cell(
        0,
        5,
        f"{match_count} fixture{'s' if match_count != 1 else ''}  ·  Generated {generated_at}",
        ln=True,
    )
    pdf.ln(8)
    pdf.set_draw_color(*BORDER)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6)


def _write_bullets(pdf: DigestPDF, title: str, body: str, *, max_lines: int = 4) -> None:
    if not body.strip():
        return
    pdf.set_font(FONT, "B", 8.5)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5, title, ln=True)
    pdf.ln(1)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    bullet_lines = [line for line in lines if line.startswith("-") or line.startswith("*")]
    if not bullet_lines:
        bullet_lines = [f"- {body.strip()}"]
    pdf.set_font(FONT, "", 8.5)
    pdf.set_text_color(*INK_MUTED)
    for line in bullet_lines[:max_lines]:
        clean = re.sub(r"^[-*]\s*", "", line)
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
        pdf.set_x(pdf.l_margin + 2)
        pdf.multi_cell(0, 4, f"  ·  {clean}")
    pdf.ln(2)


def _write_match_summary_page(
    pdf: DigestPDF,
    team_a: str,
    team_b: str,
    markdown: str,
) -> None:
    pdf.add_page()
    pdf.set_y(18)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 14)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, f"{team_a}  vs  {team_b}", ln=True)
    pdf.ln(3)

    _, dashboard = extract_dashboard_block(markdown)
    write_dashboard_panel(pdf, dashboard, compact=True)

    summary = extract_executive_summary(markdown)
    if summary:
        pdf.set_font(FONT, "B", 8.5)
        pdf.set_text_color(*INK)
        pdf.cell(0, 5, "Executive summary", ln=True)
        pdf.ln(1)
        pdf.set_font(FONT, "", 8.5)
        pdf.set_text_color(*INK_MUTED)
        plain = re.sub(r"\*\*([^*]+)\*\*", r"\1", summary)
        plain = plain.replace("\n", " ").strip()
        if len(plain) > 420:
            plain = plain[:417] + "..."
        pdf.multi_cell(0, 4.2, plain)
        pdf.ln(3)

    scenarios = extract_game_state_scenarios(markdown)
    _write_bullets(pdf, "Game-state scenarios", scenarios, max_lines=3)

    verdict = extract_verdict(markdown)
    _write_bullets(pdf, "Verdict", verdict, max_lines=3)


def generate_matchday_digest_pdf(
    report_date: str,
    reports: list[dict],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / DIGEST_FILENAME

    pdf = DigestPDF(report_date)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    _write_digest_cover(pdf, report_date, len(reports))

    for report in reports:
        _write_match_summary_page(
            pdf,
            report["team_a"],
            report["team_b"],
            report["markdown"],
        )

    pdf.output(str(pdf_path))
    logger.info("Generated matchday digest: %s", pdf_path)
    return pdf_path
