import json
import re

DASHBOARD_BLOCK_RE = re.compile(r"```dashboard\s*\n(.*?)\n```", re.DOTALL)
DASHBOARD_SECTION_RE = re.compile(
    r"## Match Dashboard\s*\n(?:```dashboard\s*\n.*?\n```\s*)?",
    re.DOTALL,
)
EXECUTIVE_SUMMARY_RE = re.compile(
    r"## Executive Summary\s*\n+(.*?)(?=\n## |\Z)",
    re.DOTALL,
)
GAME_STATE_RE = re.compile(
    r"## Game-State Scenarios\s*\n+(.*?)(?=\n## |\Z)",
    re.DOTALL,
)
VERDICT_RE = re.compile(
    r"## Verdict\s*\n+(.*?)(?=\n## |\Z)",
    re.DOTALL,
)


def extract_dashboard_block(markdown_text: str) -> tuple[str, dict | None]:
    dashboard: dict | None = None

    def _replace(match: re.Match[str]) -> str:
        nonlocal dashboard
        try:
            dashboard = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
        return ""

    stripped = DASHBOARD_BLOCK_RE.sub(_replace, markdown_text)
    stripped = DASHBOARD_SECTION_RE.sub("", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return stripped, dashboard


def extract_section(markdown_text: str, pattern: re.Pattern[str]) -> str:
    match = pattern.search(markdown_text)
    if not match:
        return ""
    text = match.group(1).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_executive_summary(markdown_text: str) -> str:
    return extract_section(markdown_text, EXECUTIVE_SUMMARY_RE)


def extract_game_state_scenarios(markdown_text: str) -> str:
    return extract_section(markdown_text, GAME_STATE_RE)


def extract_verdict(markdown_text: str) -> str:
    return extract_section(markdown_text, VERDICT_RE)


def dashboard_field(dashboard: dict | None, key: str, default: str = "—") -> str:
    if not dashboard:
        return default
    value = dashboard.get(key)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()
