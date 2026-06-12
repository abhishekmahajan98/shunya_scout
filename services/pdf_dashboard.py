from fpdf import FPDF

from services.pdf_styles import BODY_PT, BORDER, FONT, INK, SURFACE
from services.report_parse import dashboard_field


def write_dashboard_panel(
    pdf: FPDF,
    dashboard: dict | None,
    *,
    compact: bool = False,
) -> None:
    if not dashboard:
        return

    margin = pdf.l_margin
    width = pdf.w - pdf.l_margin - pdf.r_margin
    y_start = pdf.get_y()

    pdf.set_fill_color(*SURFACE)
    pdf.set_draw_color(*BORDER)
    pdf.rect(margin, y_start, width, 2 if compact else 3, style="F")

    pdf.set_xy(margin + 4, y_start + (5 if compact else 6))
    col_w = (width - 8) / 2
    line_h = BODY_PT * 0.45

    def label(text: str) -> None:
        pdf.set_font(FONT, "B", BODY_PT)
        pdf.set_text_color(*INK)
        pdf.cell(col_w, line_h, text.upper(), ln=False)

    def value(text: str, *, bold: bool = False) -> None:
        pdf.set_font(FONT, "B" if bold else "", BODY_PT)
        pdf.set_text_color(*INK)
        pdf.cell(col_w, line_h + 0.5, text[:80], ln=True)

    kickoff = dashboard_field(dashboard, "kickoff")
    venue = dashboard_field(dashboard, "venue")
    stage = dashboard_field(dashboard, "stage")

    label("Kickoff")
    pdf.set_x(margin + 4 + col_w)
    label("Venue")
    pdf.set_xy(margin + 4, pdf.get_y() + line_h)
    value(kickoff, bold=True)
    pdf.set_xy(margin + 4 + col_w, pdf.get_y() - (line_h + 0.5))
    value(venue)
    pdf.ln(2)

    pdf.set_x(margin + 4)
    label("Stage")
    pdf.set_xy(margin + 4, pdf.get_y() + line_h)
    value(stage)
    pdf.ln(3 if compact else 4)

    score = dashboard_field(dashboard, "predicted_score")
    confidence = dashboard_field(dashboard, "confidence")
    best_bet = dashboard_field(dashboard, "best_bet")

    pdf.set_x(margin + 4)
    label("Predicted score")
    pdf.set_x(margin + 4 + col_w)
    label("Confidence")
    pdf.set_xy(margin + 4, pdf.get_y() + line_h)
    value(score, bold=True)
    pdf.set_xy(margin + 4 + col_w, pdf.get_y() - (line_h + 0.5))
    value(confidence, bold=True)
    pdf.ln(2)

    pdf.set_x(margin + 4)
    label("Best bet")
    pdf.set_xy(margin + 4, pdf.get_y() + line_h)
    value(best_bet, bold=True)
    pdf.ln(3 if compact else 4)

    for field_key, field_label in (
        ("tactical_story", "Tactical story"),
        ("contrarian_angle", "Contrarian angle"),
        ("decisive_window", "Decisive window"),
    ):
        text = dashboard_field(dashboard, field_key, default="")
        if not text or text == "—":
            continue
        pdf.set_x(margin + 4)
        label(field_label)
        pdf.set_xy(margin + 4, pdf.get_y() + line_h)
        pdf.set_font(FONT, "", BODY_PT)
        pdf.set_text_color(*INK)
        pdf.multi_cell(width - 8, BODY_PT * 0.42, text)
        pdf.ln(2 if compact else 3)

    y_end = pdf.get_y() + 3
    pdf.set_draw_color(*BORDER)
    pdf.rect(margin, y_start, width, y_end - y_start, style="D")
    pdf.set_y(y_end + (3 if compact else 5))
    pdf.set_font(FONT, "", BODY_PT)
    pdf.set_text_color(*INK)
