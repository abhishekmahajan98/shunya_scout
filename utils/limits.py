import os

# Hard caps — no unbounded API loops anywhere in the pipeline.
MAX_LINEUP_REPAIR_ATTEMPTS = 1


def research_section_count() -> int:
    from graph.prompts import PERPLEXITY_RESEARCH_SECTIONS

    return len(PERPLEXITY_RESEARCH_SECTIONS)


def max_api_concurrency() -> int:
    raw = os.environ.get("MAX_API_CONCURRENCY", "").strip()
    if not raw:
        return research_section_count()
    try:
        value = int(raw)
    except ValueError:
        return research_section_count()
    return max(1, min(value, 16))


def estimate_api_calls(match_count: int) -> dict[str, int]:
    """Upper-bound LLM + API-Football calls for a pipeline run."""
    from graph.prompts import PERPLEXITY_RESEARCH_SECTIONS

    sections = len(PERPLEXITY_RESEARCH_SECTIONS)
    perplexity = match_count * sections
    gemini = match_count * (1 + MAX_LINEUP_REPAIR_ATTEMPTS)
    api_football = match_count * 12
    return {
        "perplexity_max": perplexity,
        "gemini_max": gemini,
        "api_football_max": api_football,
        "research_sections_per_match": sections,
    }
