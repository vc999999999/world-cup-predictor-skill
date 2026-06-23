# Source Helpers

Read this only when selecting sources or using bundled scripts.

## Source Roles

Use sources by evidence role, not by habit:

| Evidence | Preferred Source Type | Notes |
|---|---|---|
| Fixture identity | official competition, federation, reliable schedule | resolve exact teams and kickoff |
| 竞彩 multipliers | Sporttery webapi | primary source for final 倍率 when the user asks for 竞彩/Sporttery/poolCode |
| Auxiliary market sentiment | Polymarket, exchange prices, overseas books, odds aggregators | context only; do not use as final 竞彩倍率 |
| Lineups/availability | official match center, team channel, reliable live-score lineup page | required for player-specific markets |
| Team/player context | FBref, Transfermarkt, Understat, official stats | context only, not a substitute for current Sporttery multipliers |
| Historical conclusion context | official historical results, FBref, worldfootballR-derived data, FIFA match reports, recent form pages | use only for 过往数据结论; label source/timeframe |
| Team strength baseline | FIFA Men's World Ranking, EA FC (SoFIFA) national team ratings | primary strength proxy for data-sparse teams; FIFA ranking for official context, EA FC OVR/ATT/MID/DEF for granular profile |
| Core player star factor | `references/core-players.json` (curated EA FC elite players by national team) | qualitative signal for data-sparse teams; a single elite player (OVR >= 85) on a weak team can create an upset vector that team OVR alone misses |
| Head-to-head context | 11v11.com national team H2H records | historical matchup patterns; useful for psychological edges and style matchups |
| Odds movement signal | Sporttery odds snapshots (odds_tracker.py) | cross-run odds drift detection; reflects non-public info especially for weak-team matches |
| External news/qualitative signal | BBC Sport RSS (scripts/bbc_rss_fetch.py), other reputable news feeds | injuries, suspensions, squad rotation, tactical changes; labeled as P5 auxiliary sentiment only |

## Evidence Priority

Do not treat all football facts equally. Current fixture identity and current Sporttery multipliers are mandatory gates for 竞彩 answers. After those gates pass, rank performance/context evidence in this order:

| Priority | Evidence Type | How To Use |
|---|---|---|
| `P0` | Current-year World Cup data from the current tournament | Highest-weight football context: current tournament results, scorelines, group/table pressure, team stats, discipline, rest/travel, and squad news |
| `P1` | Current match availability | Confirmed or reputable lineup, injuries, suspensions, rotation risk, and player roles for this match |
| `P2` | Recent national-team form after the current squad cycle began | Use when current-year World Cup sample is thin; prefer competitive matches |
| `P3` | Club/player context | Use only for players expected to feature; helpful for role, minutes, xG, fitness, and form |
| `P4` | Older history and head-to-head | Context only; never outweigh current tournament evidence |
| `P5` | Auxiliary market or media sentiment | Risk/context only; never replace Sporttery multipliers or current football evidence |

When priorities conflict, name the conflict and prefer the lower-numbered priority unless the source is stale, ambiguous, or lower quality. Store the decision in `facts.json.evidence_priority` and the unresolved issue in `data_gaps`.

## Sporttery First Rule

When the request uses 竞彩 language, the final recommendation table must use Sporttery multipliers. If Sporttery does not return the requested match or pool, mark that market `blocked` or `watch`; do not substitute Polymarket, Covers, Kalshi, Bet365, or any other market as if it were Sporttery.

For "today" or all-slate World Cup requests, fetch by US fixture date using Sporttery `businessDate` and do not filter by one team:

```bash
python3 scripts/sporttery_fetch.py --pool-code had,hhad,crs,ttg,hafu --business-date 2026-06-19 --pretty
```

Use the bundled helper when it reduces manual parsing:

```bash
python3 scripts/sporttery_fetch.py --pool-code had,hhad,crs,ttg,hafu --match 美国 --pretty
```

Use `--match` only for explicit single-team, match-number, or single-match requests. For broad requests, keep every match returned for the US `businessDate`, even when one pool is missing for one match.

Pool mapping:

| poolCode | 竞彩玩法 | Key labels |
|---|---|---|
| `had` | 胜平负 | 主胜/平/客胜 |
| `hhad` | 让球胜平负 | 让胜/让平/让负 with Sporttery goal line |
| `crs` | 比分 | exact scores and 胜其他/平其他/负其他 |
| `ttg` | 总进球 | 0球 through 7+球 |
| `hafu` | 半全场 | 胜胜、胜平、胜负、平胜... |
| `hhad,had` | 混合过关候选数据 | combined access to 让球胜平负 + 胜平负 |

## Bundled Scripts

The scripts are helpers for structured data extraction:

- `scripts/sporttery_fetch.py`: Sporttery football multiplier extraction for `had`, `hhad`, `crs`, `ttg`, and `hafu`. Use this before considering non-Sporttery odds in 竞彩 requests.
- `scripts/fbref_fetch.py`: FBref match-result style data. If `--source auto` falls back to cached `worldfootballR_data`, treat it as historical context only.
- `scripts/transfermarkt_fetch.py`: Transfermarkt transfer/team/player parsing. Use carefully for national-team analysis; verify players against current squad sources.
- `scripts/understat_fetch.py`: Understat league/match xG data where supported. If a competition is unsupported, do not infer from unrelated leagues.

Install dependencies only when needed:

```bash
python3 -m pip install -r scripts/requirements.txt
```

## New Enhancement Scripts

- `scripts/fifa_rating_fetch.py`: FIFA Men's World Ranking + EA FC (SoFIFA) national team ratings. Use `--mode profile --matchup "Team A vs Team B"` for unified team strength profiles. EA FC ratings are the primary strength proxy for teams without FBref/Understat coverage.
- `scripts/h2h_fetch.py`: Head-to-head national team records from 11v11.com. Use `--home "Team A" --away "Team B"` for matchup history. Particularly valuable for weak teams where club data is unavailable.
- `scripts/odds_tracker.py`: Odds movement tracking across Sporttery fetch runs. Use `--action snapshot` after each Sporttery fetch, then `--action movement` to detect significant drift. Large movements (7%+) are strong signals for data-sparse matches.
- `scripts/bbc_rss_fetch.py`: BBC Sport football RSS fetcher with keyword-based signal extraction. Filters for injury, suspension, squad, and tactical news. Outputs structured signals with severity and category. Use `--days 3 --pretty` to get recent qualitative signals. Label outputs as P5 auxiliary sentiment only.

Usage examples:

```bash
# Team strength profiles
python3 scripts/fifa_rating_fetch.py --mode profile --matchup "Costa Rica vs Ecuador" --pretty

# Head-to-head
python3 scripts/h2h_fetch.py --home "Japan" --away "Australia" --pretty

# Odds snapshot (after sporttery_fetch.py)
python3 scripts/odds_tracker.py --action snapshot --sporttery-file facts_sporttery.json --run-dir work/world-cup-predictor/20260623-1400/

# Odds movement report
python3 scripts/odds_tracker.py --action movement --match "日本" --pretty

# BBC Sport RSS signals (last 3 days, pretty output)
python3 scripts/bbc_rss_fetch.py --days 3 --pretty --output bbc_signals.json
```

## Compact Extraction

For each source, extract only:

- source URL and retrieval time,
- fields used in the final decision, including Sporttery poolCode and update time,
- player names and statuses relevant to the markets,
- FIFA ranking position, points, and confederation,
- EA FC overall/attack/midfield/defence ratings,
- H2H total matches, win rates, goal averages, and trend,
- Odds movement direction and severity for each key market,
- Core player star factors (elite players found for each team via `references/core-players.json`),
- External news signal categories and severity (from BBC RSS or similar feeds),
- one-line note for data gaps or conflicts.

Avoid full HTML, full rosters, and broad historical tables. They make recovery harder and can cause stale evidence to look current.

## Current vs Historical Labeling

Use these labels in `source-ledger.md`:

- `current`: live or timestamped source from the current run.
- `context`: historical data that helps interpret teams or players.
- `stale`: found but outdated for the requested match.
- `blocked`: source failed or returned ambiguous data.

Only `current` Sporttery evidence can support final 竞彩倍率 claims. Auxiliary markets may support narrative context but not the final multiplier column.

Historical context can support the "过往数据结论" section, but it must be marked as historical/context and should stay compact: one to three facts per match, only when they explain the selected references or confidence.

## Final Source Presentation

Keep the final body clean for beginners. Do not scatter URLs, source names, or retrieval times through match cards or reasoning sections. In the body, use neutral labels such as `当前赛程`, `当前竞彩倍率`, `阵容信息`, and `历史背景`. Put source names, URLs, retrieval times, current/context labels, and notes in the bottom `数据来源` table immediately before `# 仅供娱乐参考`.
