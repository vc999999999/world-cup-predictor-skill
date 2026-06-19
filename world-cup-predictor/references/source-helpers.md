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

## Compact Extraction

For each source, extract only:

- source URL and retrieval time,
- fields used in the final decision, including Sporttery poolCode and update time,
- player names and statuses relevant to the markets,
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
