import json
import logging
import re

from services.formation import FORMATION_BLOCK_RE

logger = logging.getLogger(__name__)

POSITION_PATTERN = re.compile(
    r"^(?:"
    r"GK|GK\??|LB|RB|CB|LCB|RCB|LWB|RWB|"
    r"CDM|CM|CAM|LM|RM|LW|RW|ST|CF|SS|"
    r"AM|DM|DMF|AMF|WF|FB|MF|DF|FW|"
    r"UNSPECIFIED|UNKNOWN|TBD|N/A|\?|—|-"
    r")$",
    re.IGNORECASE,
)

GENERIC_NAME_PATTERN = re.compile(
    r"^(?:player|unnamed|unknown|tbd|n/a|\?|—|-)$",
    re.IGNORECASE,
)


def is_placeholder_player(name: str) -> bool:
    cleaned = name.strip()
    if not cleaned:
        return True
    if GENERIC_NAME_PATTERN.match(cleaned):
        return True
    if POSITION_PATTERN.match(cleaned):
        return True
    if len(cleaned) == 1:
        return True
    return False


def formation_player_names(data: dict) -> list[str]:
    names: list[str] = []
    for team_key in ("team_a", "team_b"):
        team = data.get(team_key, {})
        for line in team.get("lines", []):
            for player in line:
                names.append(str(player))
    return names


def formation_issues(data: dict) -> list[str]:
    issues: list[str] = []
    for team_key in ("team_a", "team_b"):
        team = data.get(team_key, {})
        label = team.get("name") or team_key
        lines = team.get("lines", [])
        players = [str(p) for line in lines for p in line]
        if len(players) != 11:
            issues.append(f"{label}: expected 11 players, got {len(players)}")
        placeholders = [p for p in players if is_placeholder_player(p)]
        if placeholders:
            issues.append(
                f"{label}: placeholder entries ({', '.join(placeholders[:5])})"
            )
    return issues


def extract_formation_data(markdown_text: str) -> dict | None:
    match = FORMATION_BLOCK_RE.search(markdown_text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def replace_formation_block(markdown_text: str, formation_data: dict) -> str:
    block = "```formation\n" + json.dumps(formation_data, indent=2) + "\n```"
    if FORMATION_BLOCK_RE.search(markdown_text):
        return FORMATION_BLOCK_RE.sub(block, markdown_text, count=1)

    header = "## Predicted Lineups"
    if header in markdown_text:
        return markdown_text.replace(
            header,
            f"{header}\n\n{block}",
            1,
        )
    return f"{header}\n\n{block}\n\n{markdown_text}"


def formation_needs_repair(markdown_text: str) -> bool:
    data = extract_formation_data(markdown_text)
    if not data:
        return True
    return bool(formation_issues(data))
