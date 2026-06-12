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

# Three text tiers for report body — size and color only, weight varies by role.
BODY_PT = 10
SUBHEADING_PT = 10
HEADING_PT = 11
BODY_LINE_HEIGHT = 1.38
BADGE_PT = 9  # formation player labels only (space-constrained)


def _rgb_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _body(**kwargs) -> TextStyle:
    return TextStyle(color=INK, font_size_pt=BODY_PT, **kwargs)


def _subheading(**kwargs) -> TextStyle:
    return TextStyle(color=INK, font_size_pt=SUBHEADING_PT, font_style="B", **kwargs)


def _heading(**kwargs) -> TextStyle:
    return TextStyle(color=INK, font_size_pt=HEADING_PT, font_style="B", **kwargs)


# fpdf2 scales heading b_margin by font size (b_margin * hsize), so keep values small.
REPORT_TAG_STYLES = {
    "p": _body(t_margin=0.3, b_margin=1.0),
    "li": _body(l_margin=3, t_margin=0.6, b_margin=0.6),
    "ul": _body(t_margin=0.6, b_margin=0.5),
    "ol": _body(t_margin=0.6, b_margin=0.5),
    "blockquote": _body(t_margin=1.0, b_margin=1.0),
    "dd": _body(l_margin=4),
    "dt": _subheading(t_margin=0.8, b_margin=0.3),
    "h1": _heading(t_margin=2, b_margin=0.4),
    "h2": _heading(t_margin=2, b_margin=0.4),
    "h3": _subheading(t_margin=1.2, b_margin=0.3),
    "h4": _subheading(t_margin=1.0, b_margin=0.3),
    "h5": _subheading(t_margin=0.8, b_margin=0.3),
    "h6": _subheading(t_margin=0.8, b_margin=0.3),
    "pre": _body(t_margin=0.8, b_margin=0.8, font_family=FONT),
    "code": FontFace(family=FONT, color=INK),
    "strong": FontFace(emphasis=TextEmphasis.B),
    "b": FontFace(emphasis=TextEmphasis.B),
    "em": FontFace(emphasis=TextEmphasis.I),
    "i": FontFace(emphasis=TextEmphasis.I),
}


def style_report_html(html: str) -> str:
    lh = BODY_LINE_HEIGHT
    html = re.sub(r"<p>", f'<p line-height="{lh}">', html)
    html = re.sub(r"<li>", f'<li line-height="{lh}">', html)
    # Reset to body size after headings so tables inherit BODY_PT, not heading size.
    html = re.sub(
        r"(</h[1-6]>)\s*<table",
        rf'\1<p line-height="{lh}"> </p><table',
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
