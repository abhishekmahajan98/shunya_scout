"""Convert API-Football lineup data into Scout formation JSON."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _short_name(full_name: str) -> str:
    parts = full_name.strip().split()
    if not parts:
        return full_name
    if len(parts) == 1:
        return parts[0]
    return parts[-1]


def _pos_rank(pos: str) -> int:
    order = {"G": 0, "D": 1, "M": 2, "F": 3}
    return order.get(pos.upper(), 2)


def start_xi_to_lines(start_xi: list[dict], formation: str) -> list[list[str]]:
    """Map API startXI + grid (or position) to attack-first lines ending with GK."""
    players: list[tuple[int, int, str, str]] = []
    for entry in start_xi:
        player = entry.get("player", {})
        name = _short_name(str(player.get("name", "")))
        if not name:
            continue
        grid = player.get("grid")
        pos = str(player.get("pos", ""))
        if grid and ":" in str(grid):
            row_s, col_s = str(grid).split(":", 1)
            try:
                players.append((int(row_s), int(col_s), name, pos))
                continue
            except ValueError:
                pass
        players.append((999, _pos_rank(pos), name, pos))

    if not players:
        return []

    has_grid = any(row < 900 for row, _, _, _ in players)
    if has_grid:
        rows = sorted({row for row, _, _, _ in players if row < 900}, reverse=True)
        lines: list[list[str]] = []
        for row in rows:
            line = [
                name
                for r, col, name, _ in sorted(
                    (p for p in players if p[0] == row),
                    key=lambda item: item[1],
                )
            ]
            if line:
                lines.append(line)
        return lines

    return _lines_from_positions(players, formation)


def _lines_from_positions(
    players: list[tuple[int, int, str, str]],
    formation: str,
) -> list[list[str]]:
    by_pos: dict[str, list[str]] = {"G": [], "D": [], "M": [], "F": []}
    for _, _, name, pos in players:
        key = pos.upper() if pos.upper() in by_pos else "M"
        by_pos[key].append(name)

    parts = [int(part) for part in formation.split("-") if part.isdigit()]
    if len(parts) >= 3:
        defenders, mids, forwards = parts[0], parts[1], sum(parts[2:])
    elif len(parts) == 2:
        defenders, mids, forwards = parts[0], parts[1], 0
    else:
        defenders = len(by_pos["D"]) or 4
        mids = len(by_pos["M"]) or 3
        forwards = len(by_pos["F"]) or 3

    lines: list[list[str]] = []
    if forwards > 0:
        lines.append(by_pos["F"][:forwards] or by_pos["F"])
    if mids > 0:
        lines.append(by_pos["M"][:mids] or by_pos["M"])
    if defenders > 0:
        lines.append(by_pos["D"][:defenders] or by_pos["D"])
    if by_pos["G"]:
        lines.append(by_pos["G"][:1])
    return [line for line in lines if line]


def lineup_entry_to_team_block(lineup: dict) -> dict:
    team = lineup.get("team", {})
    formation = str(lineup.get("formation") or "4-4-2")
    start_xi = lineup.get("startXI") or []
    return {
        "name": str(team.get("name", "Team")),
        "formation": formation,
        "lines": start_xi_to_lines(start_xi, formation),
    }


def build_formation_block(
    *,
    team_a_name: str,
    team_b_name: str,
    team_a_lineup: dict,
    team_b_lineup: dict,
    unavailable: str = "",
    source: str = "official",
) -> dict:
    from services.lineup_predict import lineup_confidence_label

    team_a = lineup_entry_to_team_block(team_a_lineup)
    team_b = lineup_entry_to_team_block(team_b_lineup)
    team_a["name"] = team_a_name
    team_b["name"] = team_b_name
    block: dict[str, Any] = {
        "team_a": team_a,
        "team_b": team_b,
        "source": source,
        "lineup_confidence": lineup_confidence_label(source),
    }
    if unavailable:
        block["unavailable"] = unavailable
    return block


def most_common_formation(lineups: list[dict]) -> str:
    counts = Counter(str(item.get("formation") or "") for item in lineups if item.get("formation"))
    if not counts:
        return "4-3-3"
    return counts.most_common(1)[0][0]
