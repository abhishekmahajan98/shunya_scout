import logging

from graph.prompts import RESEARCH_SECTIONS, SCOUT_SYSTEM
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
) -> tuple[str, str]:
    title, prompt_template = section
    logger.info("  Researching [%s] for %s vs %s", title, team_a, team_b)
    prompt = prompt_template.format(
        team_a=team_a,
        team_b=team_b,
        match_date=match_date,
    )
    result = query_perplexity(system, prompt)
    return title, result


def research_match(team_a: str, team_b: str, match_date: str) -> str:
    system = SCOUT_SYSTEM.format(match_date=match_date)

    def run_section(section: tuple[str, str]) -> tuple[str, str]:
        return _research_section(
            section,
            team_a=team_a,
            team_b=team_b,
            match_date=match_date,
            system=system,
        )

    section_results = map_parallel_ordered(list(RESEARCH_SECTIONS), run_section)
    sections = [f"## {title}\n\n{body}" for title, body in section_results]
    return "\n\n---\n\n".join(sections)
