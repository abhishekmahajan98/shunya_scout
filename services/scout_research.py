import logging

from graph.prompts import RESEARCH_SECTIONS, SCOUT_SYSTEM
from services.perplexity import query_perplexity

logger = logging.getLogger(__name__)


def research_match(team_a: str, team_b: str, match_date: str) -> str:
    sections: list[str] = []

    for title, prompt_template in RESEARCH_SECTIONS:
        logger.info("  Researching [%s] for %s vs %s", title, team_a, team_b)
        prompt = prompt_template.format(
            team_a=team_a,
            team_b=team_b,
            match_date=match_date,
        )
        system = SCOUT_SYSTEM.format(match_date=match_date)
        result = query_perplexity(system, prompt)
        sections.append(f"## {title}\n\n{result}")

    return "\n\n---\n\n".join(sections)
