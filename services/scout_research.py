import logging

from graph.prompts import PERPLEXITY_RESEARCH_SECTIONS, SCOUT_SYSTEM
from models.state import Match
from services.match_facts import gather_match_facts
from services.perplexity import query_perplexity
from utils.parallel import map_parallel_ordered

logger = logging.getLogger(__name__)


def _research_section(
    section: tuple[str, str],
    *,
    team_a: str,
    team_b: str,
    match_date: str,
    system: str,
    api_facts: str,
) -> tuple[str, str]:
    title, prompt_template = section
    logger.info("  Researching [%s] for %s vs %s", title, team_a, team_b)
    prompt = prompt_template.format(
        team_a=team_a,
        team_b=team_b,
        match_date=match_date,
    )
    prompt += (
        "\n\n--- AUTHORITATIVE API-FOOTBALL DATA (do not contradict) ---\n"
        f"{api_facts}"
    )
    result = query_perplexity(system, prompt)
    return title, result


def _perplexity_research(
    team_a: str,
    team_b: str,
    match_date: str,
    api_facts: str,
) -> str:
    system = SCOUT_SYSTEM.format(match_date=match_date)

    def run_section(section: tuple[str, str]) -> tuple[str, str]:
        return _research_section(
            section,
            team_a=team_a,
            team_b=team_b,
            match_date=match_date,
            system=system,
            api_facts=api_facts,
        )

    section_results = map_parallel_ordered(
        list(PERPLEXITY_RESEARCH_SECTIONS),
        run_section,
        max_workers=len(PERPLEXITY_RESEARCH_SECTIONS),
    )
    sections = [f"## {title}\n\n{body}" for title, body in section_results]
    return "\n\n---\n\n".join(sections)


def research_match(match: Match, match_date: str) -> tuple[str, dict | None]:
    api_facts, formation_data = gather_match_facts(match, match_date)
    perplexity_facts = _perplexity_research(
        match.team_a,
        match.team_b,
        match_date,
        api_facts,
    )
    combined = (
        f"{api_facts}\n\n---\n\n"
        f"## Qualitative Analysis (Perplexity)\n\n{perplexity_facts}"
    )
    return combined, formation_data
