import json
import logging
import os

import google.generativeai as genai

from services.formation import FORMATION_BLOCK_RE
from services.lineup import (
    extract_formation_data,
    formation_issues,
    formation_needs_repair,
    replace_formation_block,
)
from utils.api_gate import api_slot

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.5-flash"


def _configure() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)


def _extract_formation_json(text: str) -> dict | None:
    match = FORMATION_BLOCK_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def generate_lineup_formation(
    team_a: str,
    team_b: str,
    raw_scout_data: str,
) -> dict | None:
    from graph.prompts import LINEUP_FORMATION_SYSTEM, LINEUP_FORMATION_TEMPLATE

    _configure()
    user_prompt = LINEUP_FORMATION_TEMPLATE.format(
        team_a=team_a,
        team_b=team_b,
        raw_scout_data=raw_scout_data,
    )
    gemini = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=LINEUP_FORMATION_SYSTEM,
    )
    with api_slot():
        response = gemini.generate_content(user_prompt)
    text = response.text or ""
    data = _extract_formation_json(text)
    if data and not formation_issues(data):
        return data
    if data:
        logger.warning(
            "Lineup repair still has issues for %s vs %s: %s",
            team_a,
            team_b,
            formation_issues(data),
        )
    return data


def ensure_valid_formation(
    markdown_text: str,
    *,
    team_a: str,
    team_b: str,
    raw_scout_data: str,
) -> str:
    if not formation_needs_repair(markdown_text):
        return markdown_text

    existing = extract_formation_data(markdown_text)
    if existing:
        logger.warning(
            "Repairing lineup for %s vs %s (1 attempt max): %s",
            team_a,
            team_b,
            formation_issues(existing),
        )
    else:
        logger.warning(
            "Missing formation block for %s vs %s — generating (1 attempt max)",
            team_a,
            team_b,
        )

    repaired = generate_lineup_formation(team_a, team_b, raw_scout_data)
    if not repaired:
        return markdown_text

    remaining = formation_issues(repaired)
    if remaining:
        logger.warning(
            "Lineup repair incomplete for %s vs %s (not retrying): %s",
            team_a,
            team_b,
            remaining,
        )

    return replace_formation_block(markdown_text, repaired)


def analyze_match(
    team_a: str,
    team_b: str,
    raw_scout_data: str,
    match_date: str,
    *,
    formation_data: dict | None = None,
) -> str:
    from graph.prompts import ANALYST_REPORT_TEMPLATE, ANALYST_SYSTEM

    _configure()
    user_prompt = ANALYST_REPORT_TEMPLATE.format(
        team_a=team_a,
        team_b=team_b,
        match_date=match_date,
        raw_scout_data=raw_scout_data,
    )
    gemini = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=ANALYST_SYSTEM,
    )
    with api_slot():
        response = gemini.generate_content(user_prompt)
    markdown = response.text or ""

    if formation_data and not formation_issues(formation_data):
        return replace_formation_block(markdown, formation_data)

    return ensure_valid_formation(
        markdown,
        team_a=team_a,
        team_b=team_b,
        raw_scout_data=raw_scout_data,
    )
