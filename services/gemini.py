import os

import google.generativeai as genai

from graph.prompts import ANALYST_REPORT_TEMPLATE, ANALYST_SYSTEM

GEMINI_MODEL = "gemini-3.5-flash"


def _configure() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    genai.configure(api_key=api_key)


def analyze_match(
    team_a: str,
    team_b: str,
    raw_scout_data: str,
    match_date: str,
) -> str:
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
    response = gemini.generate_content(user_prompt)
    return response.text or ""
