import logging
import re
from datetime import datetime
from pathlib import Path

import markdown
from fpdf import FPDF

from services.formation import draw_formation_diagram, extract_formation_blocks
from services.pdf_dashboard import write_dashboard_panel
from services.report_parse import extract_dashboard_block
from services.pdf_styles import (
    ACCENT,
    BORDER,
    FONT,
    INK,
    INK_LIGHT,
    INK_MUTED,
    REPORT_TAG_STYLES,
    style_report_html,
)

from utils.slug import match_slug

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
LINEUPS_HEADER = "## Predicted Lineups"


class ScoutPDF(FPDF):
    def __init__(self, team_a: str, team_b: str) -> None:
        super().__init__()
        self.match_title = f"{team_a} vs {team_b}"
        self.add_font(FONT, "", str(FONT_DIR / "NotoSans-Regular.ttf"))
        self.add_font(FONT, "B", str(FONT_DIR / "NotoSans-Bold.ttf"))
        self.add_font(FONT, "I", str(FONT_DIR / "NotoSans-Italic.ttf"))
        self.add_font(FONT, "BI", str(FONT_DIR / "NotoSans-BoldItalic.ttf"))
        self.set_font(FONT, size=10)

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font(FONT, "B", 7.5)
        self.set_text_color(*INK_LIGHT)
        self.set_y(8)
        self.cell(0, 4, self.match_title, align="R")
        self.set_draw_color(*BORDER)
        self.line(self.l_margin, 13, self.w - self.r_margin, 13)
        self.set_y(16)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(*BORDER)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_font(FONT, "", 7.5)
        self.set_text_color(*INK_LIGHT)
        self.cell(0, 5, "FIFA World Cup 2026  |  Shunya Scout", align="L")
        self.set_x(self.l_margin)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def _normalize_unicode(text: str) -> str:
    replacements = {
        "\u2014": "-",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00b7": "-",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _strip_leading_h1(markdown_text: str) -> str:
    return re.sub(r"^#\s+.+?\n+", "", markdown_text.strip(), count=1)


def _write_body_html(pdf: ScoutPDF, markdown_text: str) -> None:
    if not markdown_text.strip():
        return
    html = markdown.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
    )
    pdf.set_draw_color(*BORDER)
    pdf.set_text_color(*INK)
    pdf.write_html(
        style_report_html(html),
        tag_styles=REPORT_TAG_STYLES,
        font_family=FONT,
        table_line_separators=True,
    )
    pdf.set_text_color(*INK)
    pdf.ln(1)


def _write_cover(
    pdf: ScoutPDF,
    team_a: str,
    team_b: str,
    match_date: str,
    dashboard: dict | None = None,
) -> None:
    generated_at = datetime.now().strftime("%B %d, %Y at %H:%M UTC")

    # Accent bar
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, pdf.w, 3.5, style="F")

    pdf.set_y(16)
    pdf.set_x(pdf.l_margin)

    # Kicker
    pdf.set_font(FONT, "B", 7.5)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 4, "FIFA WORLD CUP 2026  /  SHUNYA SCOUT", ln=True)

    pdf.ln(3)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "B", 22)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 11, f"{team_a}  vs  {team_b}")

    pdf.ln(1)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "", 9.5)
    pdf.set_text_color(*INK_MUTED)
    pdf.cell(0, 5, f"Match date: {match_date}", ln=True)
    pdf.set_x(pdf.l_margin)
    pdf.set_font(FONT, "", 8.5)
    pdf.set_text_color(*INK_LIGHT)
    pdf.cell(0, 5, f"Generated {generated_at}", ln=True)

    pdf.ln(5)
    y = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.3)
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.set_line_width(0.2)
    pdf.ln(6)
    pdf.set_text_color(*INK)

    if dashboard:
        write_dashboard_panel(pdf, dashboard)
    else:
        pdf.ln(2)


def _write_section_heading(pdf: ScoutPDF, title: str) -> None:
    pdf.set_x(pdf.l_margin)
    y = pdf.get_y()

    # Left accent bar
    pdf.set_fill_color(*ACCENT)
    pdf.rect(pdf.l_margin, y, 1.2, 7, style="F")

    pdf.set_x(pdf.l_margin + 4)
    pdf.set_font(FONT, "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, title, ln=True)

    y2 = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.line(pdf.l_margin, y2, pdf.w - pdf.r_margin, y2)
    pdf.ln(2)


def _split_at_lineups(markdown_text: str) -> tuple[str, str]:
    if LINEUPS_HEADER not in markdown_text:
        return markdown_text, ""
    before, after = markdown_text.split(LINEUPS_HEADER, 1)
    after = re.sub(r"^\s*\n+", "", after.lstrip())
    return before.rstrip(), after.lstrip()


def generate_match_pdf(
    markdown_text: str,
    team_a: str,
    team_b: str,
    match_date: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = match_slug(team_a, team_b)
    pdf_path = output_dir / f"{slug}.pdf"
    md_path = output_dir / f"{slug}.md"

    md_path.write_text(markdown_text, encoding="utf-8")

    body = _normalize_unicode(_strip_leading_h1(markdown_text))
    body, dashboard = extract_dashboard_block(body)
    body, formations = extract_formation_blocks(body)
    before_lineups, after_lineups = _split_at_lineups(body)

    pdf = ScoutPDF(team_a, team_b)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_top_margin(20)
    pdf.add_page()
    _write_cover(pdf, team_a, team_b, match_date, dashboard)

    if before_lineups.strip():
        _write_body_html(pdf, before_lineups)

    if formations:
        _write_section_heading(pdf, "Predicted Lineups")
        draw_formation_diagram(pdf, formations[0])

    if after_lineups.strip():
        _write_body_html(pdf, after_lineups)

    pdf.output(str(pdf_path))
    logger.info("Generated PDF: %s", pdf_path)
    return pdf_path


def pdf_path_for_match(report_date: str, team_a: str, team_b: str) -> Path:
    slug = match_slug(team_a, team_b)
    return Path("data/reports") / report_date / f"{slug}.pdf"
