import re

from fpdf.enums import TextEmphasis
from fpdf.fonts import FontFace, TextStyle

# Brand palette
INK = (17, 24, 39)
INK_MUTED = (75, 85, 99)
INK_LIGHT = (107, 114, 128)
BORDER = (229, 231, 235)
SURFACE = (249, 250, 251)
ACCENT = (5, 150, 105)
ACCENT_DARK = (6, 95, 70)
PITCH = (34, 120, 72)
PITCH_DARK = (15, 61, 38)
PITCH_LINE = (255, 255, 255)
BADGE = (255, 255, 255)
BADGE_GK = (254, 249, 195)
BADGE_BORDER = (209, 213, 219)

FONT = "NotoSans"


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


# Override fpdf2 heading defaults (large red margins) with compact section styles.
REPORT_TAG_STYLES = {
    "p": FontFace(color=INK, size_pt=10),
    "li": FontFace(color=INK, size_pt=10),
    "h2": TextStyle(
        color=INK, font_size_pt=11, font_style="B", t_margin=4, b_margin=3
    ),
    "h3": TextStyle(
        color=INK_MUTED, font_size_pt=10, font_style="B", t_margin=3, b_margin=2
    ),
    "strong": FontFace(emphasis=TextEmphasis.B),
    "b": FontFace(emphasis=TextEmphasis.B),
    "em": FontFace(emphasis=TextEmphasis.I),
    "i": FontFace(emphasis=TextEmphasis.I),
}


def style_report_html(html: str) -> str:
    html = re.sub(
        r"(</h[23]>)\s*<table",
        r"\1<br/><table",
        html,
        flags=re.IGNORECASE,
    )
    html = html.replace(
        "<table>",
        '<table width="100%" cellspacing="0" cellpadding="4" border="1">',
    )
    html = html.replace(
        "<th>",
        f'<th bgcolor="{_rgb_hex(SURFACE)}" color="{_rgb_hex(INK)}">',
    )
    html = html.replace(
        "<td>",
        f'<td bgcolor="{_rgb_hex(BADGE)}" color="{_rgb_hex(INK)}">',
    )
    return html
