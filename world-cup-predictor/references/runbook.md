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
  "data_gaps": []
}
```

Only include player names that support a decision. Do not store full squads unless the user asks. Keep `historical_context` compact: recent form, head-to-head, tournament results, team/player stats, or market-relevant trends only. Label source/timeframe and limits so older data cannot masquerade as current availability or current multipliers.

### `decision-matrix.md`

Use one row per candidate:

```markdown
| Match | Sporttery Pool | Selection | Multiplier | Implied % | Evidence | Risk | Status |
|---|---|---|---:|---:|---|---|---|
| 周五029 Team A vs Team B | had 胜平负 | 主胜 | 1.35 | 74.1 | ... | ... | stable selected |
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
