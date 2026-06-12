import json
import re

from fpdf import FPDF

from services.pdf_styles import (
    ACCENT,
    BADGE,
    BADGE_BORDER,
    BADGE_GK,
    BADGE_PT,
    BODY_PT,
    BORDER,
    FONT,
    INK,
    PITCH,
    PITCH_DARK,
    PITCH_LINE,
    SURFACE,
)

FORMATION_BLOCK_RE = re.compile(r"```formation\s*\n(.*?)\n```", re.DOTALL)

ROW_SPACING = 14
PITCH_PAD = 8
HEADER_H = 10
FOOTER_PAD = 6
BADGE_H = 8.5


def extract_formation_blocks(markdown_text: str) -> tuple[str, list[dict]]:
    formations: list[dict] = []

    def _replace(match: re.Match[str]) -> str:
        try:
            formations.append(json.loads(match.group(1)))
            return "\n"
        except json.JSONDecodeError:
            return match.group(0)

    stripped = FORMATION_BLOCK_RE.sub(_replace, markdown_text)
    return stripped, formations


def _truncate_name(name: str, max_len: int = 12) -> str:
    return name if len(name) <= max_len else f"{name[: max_len - 1]}."


def _layout_dimensions(team_a: dict, team_b: dict) -> tuple[float, float]:
    rows_a = len(team_a.get("lines", []))
    rows_b = len(team_b.get("lines", []))
    max_rows = max(rows_a, rows_b, 1)
    pitch_h = max_rows * ROW_SPACING + PITCH_PAD * 2
    total_h = HEADER_H + pitch_h + FOOTER_PAD + 2
    return pitch_h, total_h


def _draw_pitch_markings(
    pdf: FPDF, x: float, y: float, width: float, height: float
) -> None:
    pdf.set_draw_color(*PITCH_LINE)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, width, height, style="D")

    mid_y = y + height / 2
    pdf.line(x + 2, mid_y, x + width - 2, mid_y)

    cx = x + width / 2
    radius = min(width, height) * 0.11
    pdf.ellipse(cx - radius, mid_y - radius, radius * 2, radius * 2, style="D")

    box_w = width * 0.62
    box_h = height * 0.16
    box_x = x + (width - box_w) / 2
    pdf.rect(box_x, y + 2, box_w, box_h, style="D")
    pdf.rect(box_x, y + height - box_h - 2, box_w, box_h, style="D")


def _row_y(pitch_y: float, pitch_h: float, row_index: int, row_count: int) -> float:
    if row_count <= 1:
        return pitch_y + pitch_h - PITCH_PAD - BADGE_H
    playable = pitch_h - PITCH_PAD * 2 - BADGE_H
    return pitch_y + PITCH_PAD + row_index * (playable / (row_count - 1))


def _draw_player_badge(
    pdf: FPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    name: str,
    is_gk: bool,
) -> None:
    pdf.set_fill_color(*(BADGE_GK if is_gk else BADGE))
    pdf.set_draw_color(*BADGE_BORDER)
    pdf.set_line_width(0.15)
    pdf.rect(x, y, w, h, style="DF")
    pdf.set_xy(x, y + 1.8)
    pdf.set_font(FONT, "B", BADGE_PT)
    pdf.set_text_color(*INK)
    pdf.cell(w, h - 3, _truncate_name(name), align="C")


def _draw_team_pitch(
    pdf: FPDF,
    team: dict,
    x: float,
    width: float,
    start_y: float,
    pitch_h: float,
    total_h: float,
) -> None:
    name = team.get("name", "Team")
    formation = team.get("formation", "")
    lines: list[list[str]] = team.get("lines", [])
    y = start_y

    pdf.set_fill_color(*SURFACE)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.2)
    pdf.rect(x, y, width, total_h, style="DF")

    pdf.set_fill_color(*PITCH_DARK)
    pdf.rect(x, y, width, HEADER_H, style="F")
    pdf.rect(x, y + HEADER_H - 2.5, width, 2.5, style="F")

    pdf.set_xy(x + 3, y + 2.5)
    pdf.set_font(FONT, "B", BODY_PT)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(width * 0.62, 5, name, align="L")

    pill_w = 18
    pill_x = x + width - pill_w - 3
    pdf.set_fill_color(*ACCENT)
    pdf.rect(pill_x, y + 2, pill_w, 5.5, style="F")
    pdf.set_xy(pill_x, y + 2.6)
    pdf.set_font(FONT, "B", BODY_PT)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pill_w, 4.5, formation, align="C")

    pitch_x = x + 3
    pitch_y = y + HEADER_H + 2
    pitch_w = width - 6

    pdf.set_fill_color(*PITCH)
    pdf.rect(pitch_x, pitch_y, pitch_w, pitch_h, style="F")
    _draw_pitch_markings(pdf, pitch_x, pitch_y, pitch_w, pitch_h)

    row_count = len(lines)
    for row_index, line in enumerate(lines):
        players = [str(p) for p in line]
        count = len(players)
        is_gk_row = row_index == row_count - 1 and count == 1
        badge_w = max(15, min(28, (pitch_w - 8) / max(count, 1)))
        total_badges_w = badge_w * count
        row_x = pitch_x + (pitch_w - total_badges_w) / 2
        row_y = _row_y(pitch_y, pitch_h, row_index, row_count)

        for index, player in enumerate(players):
            bx = row_x + index * badge_w + 0.5
            _draw_player_badge(
                pdf, bx, row_y, badge_w - 1, BADGE_H, player, is_gk_row
            )


def draw_formation_diagram(pdf: FPDF, data: dict) -> None:
    page_width = pdf.w - pdf.l_margin - pdf.r_margin
    gap = 6
    half = (page_width - gap) / 2
    start_y = pdf.get_y()

    pitch_h, total_h = _layout_dimensions(data["team_a"], data["team_b"])

    _draw_team_pitch(
        pdf, data["team_a"], pdf.l_margin, half, start_y, pitch_h, total_h
    )
    _draw_team_pitch(
        pdf,
        data["team_b"],
        pdf.l_margin + half + gap,
        half,
        start_y,
        pitch_h,
        total_h,
    )

    pdf.set_xy(pdf.l_margin, start_y + total_h + 5)

    unavailable = data.get("unavailable", "")
    if unavailable:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(FONT, "", BODY_PT)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, BODY_PT * 0.5, f"Unavailable / Doubtful: {unavailable}")
        pdf.ln(3)

    pdf.set_font(FONT, "", BODY_PT)
    pdf.set_text_color(*INK)
