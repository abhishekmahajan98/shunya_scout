import re


def match_slug(team_a: str, team_b: str) -> str:
    raw = f"{team_a}-vs-{team_b}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug or "match-report"
