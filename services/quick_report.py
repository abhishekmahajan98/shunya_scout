SAMPLE_MARKDOWN = """\
## Executive Summary
This is a **quick test report** for {team_a} vs {team_b}. Both sides enter with \
contrasting form: {team_a} lean on structured possession while {team_b} threaten \
on transitions. The decisive battle is likely in midfield, where press resistance \
meets counter-pressing intensity.

## Match Context
- **Stage:** FIFA World Cup 2026 group stage
- **Report date:** {match_date}
- **Stakes:** Winner takes control of the group; a draw keeps both alive
- **Venue:** Neutral site, firm pitch, mild conditions expected

## Predicted Lineups

```formation
{{
  "team_a": {{
    "name": "{team_a}",
    "formation": "4-3-3",
    "lines": [
      ["Gomez", "Alvarez", "Di Maria"],
      ["Mac Allister", "Fernandez", "De Paul"],
      ["Tagliafico", "Otamendi", "Romero", "Molina"],
      ["Martinez"]
    ]
  }},
  "team_b": {{
    "name": "{team_b}",
    "formation": "4-2-3-1",
    "lines": [
      ["Mbappe"],
      ["Rabiot", "Griezmann", "Dembele"],
      ["Camavinga", "Tchouameni"],
      ["Hernandez", "Upamecano", "Saliba", "Kounde"],
      ["Maignan"]
    ]
  }},
  "unavailable": "{team_a}: none reported. {team_b}: one midfielder monitored."
}}
```

## Head-to-Head
- **Record (last 5):** 2 {team_a} wins, 1 draw, 2 {team_b} wins
- **Last meeting:** 2-1 to {team_b} in a competitive friendly (2024)
- **Pattern:** Tight games, average 2.4 goals per match, both teams scored in 4/5

## Tactical Breakdown

### {team_a}
Build through the double pivot, wide overloads, and aggressive full-back pushes. \
Vulnerable when turnovers occur in the attacking third.

### {team_b}
Compact 4-2-3-1, fast vertical progression through Mbappe, and rest defence \
that invites crosses from wide areas.

## Key Battles on the Pitch
- Mac Allister vs Tchouameni: tempo control and press escape
- Molina vs Dembele: 1v1 defending on the right flank
- Romero vs Mbappe: space management in behind

## Player Form Ledger

### {team_a}
- **Hot:** Alvarez - 3 goals in last 4, high xG volume
- **Cold:** Gomez - limited end product, 0 G/A in last 3

### {team_b}
- **Hot:** Mbappe - 4 goal contributions in last 5
- **Cold:** Rabiot - subdued creative output recently

## Players to Watch
- **{team_a}:** Enzo Fernandez - dictates rhythm and recycles possession under press
- **{team_b}:** William Saliba - organizes the back line and wins key duels

## Set Pieces & Transition Threats
{team_a} carry aerial threat from corners via Otamendi and Romero. \
{team_b} are lethal within 8 seconds of winning the ball in the middle third.

## Advanced Metrics & Trends
- {team_a} xG per game (last 5): 1.82
- {team_b} xG per game (last 5): 1.95
- {team_a} PPDA: 9.8 (moderate press)
- {team_b} PPDA: 11.2 (selective press)

## Betting Intelligence
| Market | Line | Implied read |
|---|---|---|
| 1X2 | {team_a} +145 / Draw +240 / {team_b} +170 | Slight edge to open game |
| Asian Handicap | {team_b} -0.25 | Market leans narrow away win |
| Over/Under 2.5 | Over -118 / Under +100 | Goals expected |

**Value angles:**
1. *Over 2.5 goals* - both sides create high-quality chances and concede in transition
2. *Mbappe anytime scorer* - primary outlet in open transitions

## Verdict
- **Predicted scoreline:** 1-2 or 2-2 (medium confidence)
- **Decisive factor:** Which side wins the first 15 minutes after halftime
- **Risk factors:** Early red card, or {team_a} failing to convert territorial dominance
"""


def build_sample_markdown(team_a: str, team_b: str, match_date: str) -> str:
    return SAMPLE_MARKDOWN.format(
        team_a=team_a,
        team_b=team_b,
        match_date=match_date,
    )
