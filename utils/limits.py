import os

# Hard caps — no unbounded API loops anywhere in the pipeline.
MAX_LINEUP_REPAIR_ATTEMPTS = 1
DEFAULT_MAX_MATCHES_PER_RUN = 8
def research_section_count() -> int:
    from graph.prompts import RESEARCH_SECTIONS

    return len(RESEARCH_SECTIONS)


def max_api_concurrency() -> int:
    raw = os.environ.get("MAX_API_CONCURRENCY", "").strip()
    if not raw:
        return research_section_count()
    try:
        value = int(raw)
    except ValueError:
        return research_section_count()
    return max(1, min(value, 16))


def max_matches_per_run() -> int:
    raw = os.environ.get("MAX_MATCHES_PER_RUN", "").strip()
    if not raw:
        return DEFAULT_MAX_MATCHES_PER_RUN
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_MATCHES_PER_RUN
    return max(1, min(value, 20))


def estimate_api_calls(match_count: int) -> dict[str, int]:
    """Upper-bound LLM calls for a pipeline run (for logging / cost awareness)."""
    from graph.prompts import RESEARCH_SECTIONS

    sections = len(RESEARCH_SECTIONS)
    perplexity = 1 + match_count * sections  # scheduler + scout sections per match
    gemini = match_count * (1 + MAX_LINEUP_REPAIR_ATTEMPTS)  # analyst + lineup repair
    return {
        "perplexity_max": perplexity,
        "gemini_max": gemini,
        "research_sections_per_match": sections,
    }
