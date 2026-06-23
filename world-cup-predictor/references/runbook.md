# Runbook

This file defines the data collection and recovery workflow. Read it before collecting data or when resuming a partial run.

## Run Folder

Create one fresh folder per request:

```text
work/world-cup-predictor/YYYYMMDD-HHMM/
```

For World Cup requests hosted in the United States, derive `today` from the US fixture date, not the runtime or user timezone. Use US/Eastern as the canonical date unless the user specifies another US timezone, then show the corresponding Asia/Shanghai date/time in the answer. Sporttery `businessDate` should match this US fixture date.

## Files To Maintain

### `source-ledger.md`

Append one row per source:

```markdown
| Step | Source | URL | Retrieved At | Current? | Notes |
|---|---|---|---|---|---|
| fixture | FIFA | ... | 2026-06-19 22:20 Asia/Shanghai | yes | official match page |
```

Use `Current? = no` for historical context, cached data, old FBref/Understat tables, or anything without live Sporttery multipliers.

### `facts.json`

Keep compact structured evidence:

```json
{
  "scope": {
    "mode": "all_us_date|single_match",
    "us_fixture_date": "",
    "us_timezone": "America/New_York",
    "asia_shanghai_date": "",
    "status": "verified|ambiguous|missing"
  },
  "fixtures": [
    {
      "match_num": "",
      "home": "",
      "away": "",
      "competition": "",
      "kickoff_us": "",
      "kickoff_asia_shanghai": "",
      "status": "verified|ambiguous|missing"
    }
  ],
  "sporttery_odds": [
    {
      "poolCode": "",
      "poolName": "",
      "selection": "",
      "multiplier": null,
      "source": "",
      "retrieved_at": "",
      "sporttery_updated_at": "",
      "implied_probability": null
    }
  ],
  "auxiliary_markets": [],
  "evidence_priority": [
    {
      "rank": "P0",
      "label": "current-year World Cup data",
      "facts_used": []
    }
  ],
  "historical_context": [
    {
      "match": "",
      "source": "",
      "timeframe": "",
      "facts": [],
      "conclusion": "",
      "limits": ""
    }
  ],
  "upset_radar": [
    {
      "match": "",
      "label": "low|medium|high|insufficient",
      "cold_score_refs": [],
      "signals": [],
      "limits": ""
    }
  ],
  "players": [
    {
      "name": "",
      "team": "",
      "status": "confirmed|likely|doubtful|out|unknown",
      "role": "",
      "note": ""
    }
  ],
  "team_notes": [],
  "data_gaps": [],
  "team_profiles": [
    {
      "team": "",
      "fifa_ranking": {
        "rank": null,
        "points": null,
        "confederation": "",
        "rank_change": null
      },
      "eafc_rating": {
        "overall": null,
        "attack": null,
        "midfield": null,
        "defence": null
      },
      "strength_tier": "elite|strong|mid|mid-low|weak",
      "is_data_sparse": false,
      "data_quality": "good|partial|insufficient"
    }
  ],
  "odds_movement": [
    {
      "match": "",
      "pool": "",
      "selection": "",
      "opening_odds": null,
      "current_odds": null,
      "movement": null,
      "movement_pct": null,
      "direction": "",
      "severity": "",
      "signal": ""
    }
  ],
  "h2h_data": [
    {
      "match": "",
      "home": "",
      "away": "",
      "total_matches": null,
      "home_wins": null,
      "draws": null,
      "away_wins": null,
      "home_goals_avg": null,
      "away_goals_avg": null,
      "goal_total_avg": null,
      "recent_5": [],
      "trend": ""
    }
  ],
  "core_players": {
    "home": [
      {
        "name": "",
        "club": "",
        "position": "",
        "ovr": null,
        "tier": "elite|star|notable"
      }
    ],
    "away": []
  },
  "news_signals": [
    {
      "title": "",
      "category": "injury|suspension|squad|tactics|illness|general",
      "severity": "high|medium|low",
      "teams_mentioned": [],
      "pubDate": "",
      "link": ""
    }
  ]
}
```

Only include player names that support a decision. Do not store full squads unless the user asks. Keep `historical_context` compact: recent form, head-to-head, tournament results, team/player stats, or market-relevant trends only. Label source/timeframe and limits so older data cannot masquerade as current availability or current multipliers. Use `evidence_priority` to record why current-year World Cup data was weighted above older or proxy evidence. Use `upset_radar` to store the compact reasoning behind `爆冷雷达`, especially exact-score (`crs`) cold-score references and missing score data.

### `analysis-brief.md`

Create this compressed model-input file when the request has multiple matches, many sources, or long extracted text:

```markdown
## Scope
- US fixture date:
- Shanghai display date:
- Matches covered:

## Current Facts
- Match identity:
- Current odds:
- Availability:

## Priority Evidence
- P0 current-year World Cup:
- P1 current availability:
- P2 recent national-team:
- P3 club/player context:
- P4 older history:

## Decisions
| Match | Main Direction | Score Refs | Upset Radar | Selected References | Key Risk |
|---|---|---|---|---|---|

## Gaps
- ...
```

Keep it under roughly 150 lines. Do not paste raw HTML, full tables, full squads, or duplicate source URLs already in `source-ledger.md`. Final reasoning should use this compressed brief plus `facts.json`, not raw extraction dumps.

### `decision-matrix.md`

Use one row per candidate:

```markdown
| Match | Sporttery Pool | Selection | Multiplier | Implied % | Evidence | Upset Signal | Risk | Status |
|---|---|---|---:|---:|---|---|---|---|
| 周五029 Team A vs Team B | had 胜平负 | 主胜 | 1.35 | 74.1 | ... | 冷门低 | ... | stable selected |
```

Status values: `stable selected`, `high selected`, `watch`, `rejected`, `blocked`.

### `handoff.md`

Write this before final or when stopping:

```markdown
## Verified
- ...

## Missing Or Conflicting
- ...

## Decisions
- Stable:
- High 1:
- High 2:

## Resume Next
- ...
```

## Recovery

When resuming:

1. Read `handoff.md`.
2. Re-check any source marked missing, conflicting, or stale.
3. Re-fetch Sporttery multipliers for the full US `businessDate` if the previous retrieval was not from the current turn.
4. Update `source-ledger.md`, `facts.json`, and `decision-matrix.md`.
5. Only then write or revise the final answer.

## Skill Handoff

When another skill, agent, or later session needs to continue the work, hand off the run folder path and `handoff.md`. The receiving skill should treat `facts.json` and `source-ledger.md` as compact evidence, then re-fetch any current Sporttery multipliers or availability data before making recommendations.

## Data Freshness Gate

Current Sporttery multipliers and current fixture verification are mandatory for 竞彩 odds-based references. Broad "today" requests must list every fixture on the US fixture date even when some matches have missing pools. Historical player/team data may support reasoning, but it cannot substitute for current Sporttery multipliers or current availability. Polymarket and other auxiliary markets cannot replace missing Sporttery data.

## Evidence Priority Gate

After mandatory current fixture and current multiplier checks pass, rank football-performance evidence in this order:

1. `P0 current-year World Cup`: current tournament matches, group situation, team stats, scorelines, discipline, travel/rest, and current squad news from this year's World Cup.
2. `P1 current availability`: confirmed or reputable current lineup, injuries, suspensions, rotation, and player roles for the specific match.
3. `P2 recent national-team form`: matches after the current squad cycle began, especially competitive fixtures.
4. `P3 club/player context`: club-season form, xG, minutes, role, and fitness only for players expected to feature.
5. `P4 older history`: head-to-head, older tournament records, long-run style, or coach history.
6. `P5 auxiliary sentiment`: exchange or overseas market sentiment, social/news context, and other non-Sporttery signals.

When these conflict, prefer the lower-numbered priority unless there is a named data-quality reason not to. Record the conflict in `facts.json.data_gaps` or `decision-matrix.md` rather than smoothing it away.

## Weak-Team Data Enhancement Strategy

When one or both teams in a match are data-sparse (FIFA rank 80+, EA FC OVR < 68, or limited recent match records), apply this enhanced workflow:

1. **Always fetch team profiles**: run `fifa_rating_fetch.py --mode profile --matchup "Team A vs Team B"` for every match. EA FC game ratings provide a structured strength baseline even for teams with no FBref/Understat coverage.
2. **Weight EA FC ratings higher for weak teams**: when real match data (P0-P2) is sparse, the EA FC overall rating differential becomes a primary strength signal. A 10+ OVR gap strongly suggests a quality difference.
3. **Fetch H2H for every match**: run `h2h_fetch.py --home "Team A" --away "Team B"` to check for historical patterns. Some weak teams have psychological edges over stronger opponents.
4. **Snapshot odds early**: run `odds_tracker.py --action snapshot` after the first Sporttery fetch, then compare with `--action movement` before finalizing. Large odds movements often reflect non-public information that is especially valuable for data-sparse matches.
5. **Flag contradictions**: if EA FC ratings suggest one team is much stronger but odds have drifted toward the weaker team, flag this as a potential upset signal in the 爆冷雷达.
6. **Look up core player star factors**: check `references/core-players.json` for any elite (OVR >= 85) or star (OVR >= 83) players on either team. A data-sparse team with an elite star (e.g., Son Heung-min on South Korea, Szoboszlai on Hungary) can create an upset vector that pure team OVR misses. Record matched players in `facts.json.core_players`. See `references/output-contract.md` § Core Player Upset Signals.
7. **Fetch external news signals**: run `scripts/bbc_rss_fetch.py --days 3 --pretty` to get recent injury, suspension, squad, and tactical news. Record signals matching either team in `facts.json.news_signals`. Label these as P5 auxiliary sentiment; they can downgrade confidence (injury to key player) or upgrade it (key rival star absent). See `references/source-helpers.md` § External news/qualitative signal.

## Pre-Final Validation Hook

Before finalizing, run:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/
```

If a `final.md` draft exists in the run folder, include it:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/ --final-answer work/world-cup-predictor/YYYYMMDD-HHMM/final.md
```

The hook checks required run files, Sporttery primary-source evidence, selected-row multipliers, handoff structure, and the required final disclaimer line when a draft answer is supplied. Fix errors before final output. Keep warnings visible as data limitations.
