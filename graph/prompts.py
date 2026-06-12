SCOUT_SYSTEM = (
    "You are an elite football scout and tactical analyst preparing intelligence "
    "for a World Cup betting desk. Search the web exhaustively. Be specific: "
    "name players, cite dates, quote stats, and note sources. Today's date "
    "is {match_date}. The tournament is FIFA World Cup 2026. If data is "
    "uncertain, say so — never invent facts."
)

SCOUT_LINEUPS = """\
Research predicted lineups for {team_a} vs {team_b} at the FIFA World Cup 2026.

Today's date: {match_date}.

Cover in depth:
1. Full confirmed/provisional World Cup 2026 squads for both teams.
2. Predicted starting XIs (formation + 1–11) based on the most recent competitive matches.
3. Actual starting lineups from each team's last 3 games in this tournament or qualifiers — note any changes.
4. Injuries, suspensions, fitness doubts, and players returning from knocks.
5. Likely bench impact subs and rotation risk given the match date and group/knockout context.
6. Goalkeeper situation and defensive partnership stability.

Cite sources and dates for every lineup claim."""

SCOUT_H2H = """\
Research head-to-head history for {team_a} vs {team_b}.

Today's date: {match_date}. Focus on World Cup 2026 context but include relevant historical meetings.

Cover:
1. Full H2H record (wins, draws, goals) and last 5 meetings with scores and dates.
2. World Cup / major tournament meetings specifically.
3. Patterns: who tends to score first, clean sheets, cards, goals per game.
4. Tactical trends from past meetings (formations used, how games were won).
5. Psychological edge or narrative (revenge, underdog runs, etc.)."""

SCOUT_PLAYER_FORM = """\
Research individual player form for {team_a} vs {team_b} at World Cup 2026.

Today's date: {match_date}.

For EACH team, provide:
1. **In-form players** (last 3–5 games): goals, assists, key stats, standout performances.
2. **Out-of-form / struggling players**: poor recent output, errors, minutes concerns.
3. **Player to Watch** — one per team: why they are the decisive factor tactically today.
4. xG/xA or comparable advanced metrics where available.
5. Minutes played, fatigue, and yellow-card accumulation risk.

Be player-specific. No generic praise."""

SCOUT_TACTICAL = """\
Research tactical profiles for {team_a} vs {team_b} at World Cup 2026.

Today's date: {match_date}.

Cover for BOTH teams:
1. Primary formation(s) and in-possession shape.
2. Build-up patterns: how they progress from back to final third.
3. Pressing system: PPDA, high/mid/low block, trigger points.
4. Defensive vulnerabilities: spaces exploited, set-piece weakness, transition exposure.
5. Set-piece threat (corners, free kicks): key takers and aerial targets.
6. Transition game: counter-attack speed vs defensive rest defence.
7. How their style likely clashes in this specific matchup."""

SCOUT_CONTEXT = """\
Research match context for {team_a} vs {team_b} at World Cup 2026.

Today's date: {match_date}.

Cover:
1. Group/knockout stage situation: points, goal difference, what each team needs.
2. Recent team form: last 5 results with scores for both sides.
3. Venue, kick-off time, weather/pitch conditions if relevant.
4. Travel, rest days, and fixture congestion.
5. Manager quotes or press conference signals on approach.
6. Referee appointment and card/foul tendencies if announced.
7. Crowd / home-advantage dynamics for 2026 host cities."""

SCOUT_BETTING = """\
Research betting markets for {team_a} vs {team_b} at World Cup 2026.

Today's date: {match_date}.

Cover:
1. Current consensus odds: Moneyline (1X2), Asian Handicap, Over/Under 2.5 (and 3.5 if available).
2. Implied win probabilities from odds.
3. Any significant line movement in the last 48 hours and why.
4. Prop market angles: anytime goalscorer, cards, corners if data exists.
5. Where sharp/public money may differ from the line (if reported).
6. Historical betting trends in this fixture type.

Cite bookmaker consensus or odds aggregators."""

RESEARCH_SECTIONS: list[tuple[str, str]] = [
    ("Predicted Lineups & Squads", SCOUT_LINEUPS),
    ("Head-to-Head", SCOUT_H2H),
    ("Player Form & Players to Watch", SCOUT_PLAYER_FORM),
    ("Tactical Analysis", SCOUT_TACTICAL),
    ("Match Context", SCOUT_CONTEXT),
    ("Betting Markets", SCOUT_BETTING),
]

ANALYST_SYSTEM = (
    "You are the lead match analyst for an elite football intelligence unit. "
    "You write the definitive pre-match scout report used by professional "
    "bettors and analysts. Your reports are comprehensive, technical, and "
    "data-driven — but structured for fast scanning. "
    "Be opinionated: assign confidence tiers (High, Medium, or Low), name a "
    "clear best bet, and include one contrarian angle where the market may be "
    "wrong. "
    "Output ONLY valid GitHub-flavored Markdown. Rules: use ## and ### headers "
    "(never # — the PDF cover already has the title); use - for bullets; use "
    "**bold** for emphasis; tables must use proper | column | syntax with a "
    "header separator row; leave a blank line before every header and table; "
    "no bold or italic inside table cells; no HTML tags; no code fences around "
    "the full report except the required ```dashboard and ```formation blocks. "
    "Name players and cite specific stats from the research. Do not invent "
    "data not present in the research. Where the research is thin, flag the gap "
    "explicitly."
)

ANALYST_REPORT_TEMPLATE = """\
Synthesize the following raw scouting research into the world's best pre-match \
scout report for **{team_a} vs {team_b}** (World Cup 2026, report date: {match_date}).

--- RAW RESEARCH ---
{raw_scout_data}
--- END RESEARCH ---

Write the final report using EXACTLY this structure (start at ## — do NOT repeat the title):

## Match Dashboard

Output ONLY a ```dashboard JSON block in this section (no other text). Use real data from research.

```dashboard
{{
  "kickoff": "Local kickoff time with timezone",
  "venue": "Stadium, city",
  "stage": "Group/knockout stage and what is at stake",
  "predicted_score": "e.g. 2-1",
  "confidence": "High, Medium, or Low",
  "best_bet": "Single clearest betting position with line",
  "tactical_story": "One sentence: the decisive tactical narrative",
  "contrarian_angle": "One sentence: where consensus or the market may be wrong",
  "decisive_window": "When the match is most likely to turn (e.g. minutes 55-70)"
}}
```

## Executive Summary
3–4 sentences: stakes, likely narrative, and the single most important tactical story.

## Game-State Scenarios
- **If {team_a} scores first:** how the game state changes tactically and for betting
- **If {team_b} scores first:** how the game state changes tactically and for betting
- **If level at halftime:** most likely second-half adjustment and edge

## Match Context
- Stage, standings, what each team needs
- Venue, conditions, rest/rotation factors

## Predicted Lineups

Output a ```formation JSON block (and nothing else in this section except that block). \
Lines run attack-to-goal (forwards first, goalkeeper last). Each line is left-to-right \
on the pitch. Use real predicted player names only.

```formation
{{
  "team_a": {{
    "name": "{team_a}",
    "formation": "4-3-3",
    "lines": [
      ["LW", "ST", "RW"],
      ["CM", "CM", "CM"],
      ["LB", "CB", "CB", "RB"],
      ["GK"]
    ]
  }},
  "team_b": {{
    "name": "{team_b}",
    "formation": "4-2-3-1",
    "lines": [
      ["ST"],
      ["LW", "CAM", "RW"],
      ["CDM", "CDM"],
      ["LB", "CB", "CB", "RB"],
      ["GK"]
    ]
  }},
  "unavailable": "List injuries, suspensions, and doubts for both teams"
}}
```

## Head-to-Head
- Record and recent meetings with scores
- Key H2H patterns and what history suggests today

## Tactical Breakdown

### {team_a}
Formation, build-up, pressing, strengths, weaknesses

### {team_b}
Formation, build-up, pressing, strengths, weaknesses

## Key Battles on the Pitch
3–4 specific matchup duels that will decide the game (e.g. winger vs full-back)

## Player Form Ledger

### {team_a}
- **Hot:** players in form with evidence
- **Cold:** players struggling with evidence

### {team_b}
- **Hot:** players in form with evidence
- **Cold:** players struggling with evidence

## Players to Watch
- **{team_a}:** [Player] — why they matter today
- **{team_b}:** [Player] — why they matter today

## Set Pieces & Transition Threats
Who wins dead balls, who is dangerous on the counter

## Advanced Metrics & Trends
xG, chance quality, possession trends, defensive metrics — whatever the research supports

## Betting Intelligence
| Market | Line | Implied read |
|---|---|---|
| 1X2 | ... | ... |
| Asian Handicap | ... | ... |
| Over/Under | ... | ... |

**Value angles:** 2–3 reasoned betting positions with justification (not generic). Tag each with (High), (Medium), or (Low) confidence.

## Verdict
- **Predicted scoreline range** with confidence tier (High / Medium / Low)
- **Best bet today** — repeat the single strongest position
- **Most likely decisive factor**
- **Contrarian risk** — what could make the consensus wrong
- **Risk factors** that could flip the script
"""
