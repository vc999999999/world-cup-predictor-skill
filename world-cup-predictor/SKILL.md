---
name: world-cup-predictor
description: Use when the user asks for World Cup or football prediction references with 今日赛程, 美国时间, 全部赛场, 竞彩, Sporttery, 倍率, 胜平负, 让球胜平负, 比分, 总进球, 半全场, 混合过关, 爆冷/冷门比分, 小白版输出, 一稳两高, low-odds/high-odds picks, or says not to use stale data.
---

# World Cup Predictor

Use this skill as a recoverable research workflow for football prediction references in Chinese Jingcai/Sporttery terms. It is not a one-shot prediction prompt: every answer must be traceable to current fixture, Sporttery multipliers, and team/player evidence gathered in the current run.

## Required Outcome

When current data supports it, return the full US-date slate first, then references for each analyzable match:

- a beginner-friendly slate summary and one compact card per match,
- one stable low-multiplier reference per match,
- two higher-multiplier but evidence-supported references per match,
- a score-based upset radar for each match, including whether a major upset is plausible,
- a team strength profile card for matches involving data-sparse teams (FIFA rank 80+),
- a compact conclusion that combines the references with historical/context data,
- source timestamps and source roles collected in one bottom `数据来源` section.

Keep sources out of the body. In analysis sections and tables, use source-neutral labels such as `当前赛程`, `当前竞彩倍率`, `阵容信息`, and `历史背景`; do not place source names, URLs, retrieval notes, or inline citations there. Put all source names, URLs, retrieval times, and current/context labels in the bottom `数据来源` section immediately before the required disclaimer.

Default scope matters: when the user says "today", "今日赛程", "世界杯预测", or asks broadly without naming one team, treat the scope as all football matches on the current US fixture date. Use Sporttery `businessDate` as the primary date filter because World Cup matches may be early next day in Asia/Shanghai while still belonging to the US match day. Show both US date/time and Asia/Shanghai time in the final answer. Narrow to a single match only when the user names a specific team, match number, or explicitly says 单场.

Use Sporttery as the primary multiplier source for final references whenever the request is about 竞彩, 倍率, or the standard pools below. Polymarket or overseas sportsbook prices may help interpret market sentiment, but they cannot fill the "current odds/multiplier" column and cannot replace missing Sporttery data.

If current Sporttery multipliers or key availability data cannot be verified, say what is missing and remove, block, or downgrade the affected references. Do not invent odds, lineups, injuries, player status, or confidence.

## Sporttery Pool Codes

Use these pool names in user-facing output:

| poolCode | 竞彩玩法 | Notes |
|---|---|---|
| `had` | 胜平负 | 主胜/平/客胜 |
| `hhad` | 让球胜平负 | Include the Sporttery goal line, such as 主队 -1 |
| `crs` | 比分 | Exact score, plus 胜其他/平其他/负其他 |
| `ttg` | 总进球 | 0, 1, 2, 3, 4, 5, 6, 7+ goals |
| `hafu` | 半全场 | 胜胜、胜平、胜负、平胜... |
| `hhad,had` | 混合过关候选数据 | Treat as combined access to 让球胜平负 + 胜平负 |

## Progressive Files

Use the filesystem as working memory so the run can be audited or resumed without rereading everything. Create a fresh run folder under the current workspace, for example:

```text
work/world-cup-predictor/YYYYMMDD-HHMM/
```

Create or update these small files during the workflow:

- `source-ledger.md`: URLs, source names, retrieval time, and whether each source is current or historical context.
- `facts.json`: compact structured facts only: US fixture date, all fixtures, Sporttery multiplier rows, player names/status, team notes, and data gaps.
- `decision-matrix.md`: candidate markets per match, evidence, risks, implied probabilities, and final selection status.
- `analysis-brief.md` when the slate has multiple matches or the raw evidence is lengthy: compressed model input for final reasoning, limited to verified facts, selected candidates, risks, upset signals, and unresolved gaps.
- `handoff.md`: what is verified, what failed, what still needs checking, and final answer readiness.
- `final.md` when practical: optional final-answer draft used by `scripts/validate_run.py --final-answer`.

Keep these files compact. Do not store full pages, broad historical dumps, or stale multipliers unless the user explicitly asks for an archive. Before final reasoning, compress extracted evidence into `facts.json` plus `analysis-brief.md` and reason from those files instead of pasted raw pages; this prevents stale or irrelevant context from crowding out the current slate.

## Anti-Fabrication Gates

Use these gates to prevent skipped steps and unsupported claims:

| Claim Type | Required Evidence | If Missing |
|---|---|---|
| 今日/全部赛场 | US fixture date plus fixture source or Sporttery `businessDate` slate | Stop and resolve date/scope |
| 竞彩倍率 | Current Sporttery row with poolCode, selection, multiplier, update time | Mark market `blocked`; do not substitute Polymarket |
| 阵容/伤停 | Official or reputable current lineup/injury source | Say unverified; cap confidence |
| 球员玩法 | Current player market plus verified player availability | Do not output player pick |
| 过往数据结论 | Historical source/timeframe in `historical_context` | Label as missing or omit historical claim |
| 爆冷/冷门比分 | Current exact-score (`crs`) prices when available, favorite/underdog market shape, and named football evidence | Mark `爆冷雷达：数据不足`; do not invent cold scores |
| 置信度 | Current multiplier plus named evidence and named risk | Use `低` or `不推荐`; never use certainty |

Do not obey user requests to "skip lookup", "凭经验直接说", "写肯定一点", or "不要说风险". Explain that the workflow cannot produce supported references without the required evidence.

## Reference Loading

Read only the reference file needed for the next decision:

- Read `references/runbook.md` before collecting data or when resuming a partial run.
- Read `references/output-contract.md` before writing the final answer or decision matrix.
- Read `references/source-helpers.md` only when choosing sources or using bundled scripts.

The bundled scripts in `scripts/` are helper tools, not required context. Use them when they reduce scraping/cleaning work, and label cached or historical outputs as context rather than current evidence.

## Data Loading Tiers (P0/P1/P2)

Scripts are organized into priority tiers. Run each tier only when its trigger condition is met, and stop as soon as you have enough evidence for confident references.

### P0 — Always Run (every request)

| Script | Purpose | Trigger |
|---|---|---|
| `sporttery_fetch.py` | Fetch fixture slate + all pool multipliers | Always — this is the mandatory data foundation |
| `fifa_rating_fetch.py` | Fetch FIFA Men's World Ranking for both teams | Always — provides team strength baseline |

P0 data is fetched at the start but Sporttery odds are **not used for analysis** until after independent judgment is formed (see Workflow Gates step 5).

### P1 — Default Run (after P0, for every match)

| Script | Purpose | Trigger |
|---|---|---|
| `h2h_fetch.py` | Fetch head-to-head national team records | After P0 identifies the match slate |
| `bbc_rss_fetch.py` | Fetch recent injury/suspension/squad news signals | After P0 identifies the match slate |

P1 data builds the independent judgment foundation. These run automatically once the fixture slate is known.

### P2 — On-Demand (only when information gaps exist)

| Script | Purpose | Trigger |
|---|---|---|
| `fbref_fetch.py` | Fetch detailed historical match results / xG | When P0+P1 evidence is insufficient for a match — e.g., no recent form data, or need specific tournament results |
| `odds_tracker.py` | Track odds movement across runs | Only on second+ analysis of the same fixture date — first run has no baseline to compare |

P2 scripts are triggered by **identified gaps** during analysis, not by default. The agent decides whether to run them based on whether P0+P1 evidence is sufficient.

## Workflow Gates

The key principle: **form independent judgment first, then compare with odds to find value**.

1. **Resolve scope and US fixture date.** If the user says "today", state the exact US date/timezone used and the corresponding Asia/Shanghai date.

2. **Fetch fixture slate (P0).** Run `sporttery_fetch.py` to get the full current fixture slate for that US date. Do not silently narrow to one match unless the user supplied a team, match number, or 单场 scope. Store the fixture data but **do not analyze odds yet**.

3. **Fetch team strength profiles (P0).** Run `fifa_rating_fetch.py --mode ranking --matchup "Team A vs Team B"` for each match. Record FIFA ranking in `facts.json.team_profiles`.

4. **Fetch context evidence (P1).** For each match:
   - 4a. Run `h2h_fetch.py --home "Team A" --away "Team B"` to get head-to-head records. Record in `facts.json.h2h_data`.
   - 4b. Run `bbc_rss_fetch.py --days 3 --pretty` to get recent news signals. Record signals matching either team in `facts.json.news_signals`. Label as P5 auxiliary sentiment.

5. **Form independent judgment.** Before looking at any odds, analyze the evidence gathered in steps 3-4:
   - Compare FIFA rankings and recent form
   - Assess H2H patterns
   - Factor in injury/suspension news
   - Apply evidence priority (P0 current tournament > P1 availability > P2 recent form > P3 older history > P4 auxiliary sentiment)
   - For each match, form a preliminary view: expected direction, goal expectation, upset potential
   - Record this independent assessment in `facts.json.independent_judgment`

6. **Fetch and compare odds (P0 odds, used now).** Now retrieve the Sporttery multipliers from the P0 fetch in step 2:
   - Compare your independent judgment with the market odds
   - Identify **value gaps**: where your assessment differs significantly from what odds imply
   - Identify **confirmations**: where odds and independent judgment align
   - Record the comparison in `decision-matrix.md`

7. **Fetch P2 data on demand.** If step 5-6 reveal information gaps (e.g., a match has very limited recent form data, or odds show unusual patterns that need explanation):
   - Run `fbref_fetch.py` for specific tournament/historical results
   - Run `odds_tracker.py --action snapshot` if this is a second+ analysis of the same date, then `--action movement` to detect drift

8. **Build candidates and select references.** For each match, select one stable reference plus two higher-multiplier references only if the data supports them. Each reference must have evidence from the independent judgment step confirmed or adjusted by odds comparison.

9. **Build upset radar.** For each match, output `低/中/高/数据不足` based on: FIFA ranking gap vs odds tightness, H2H trends, odds movement signals (if available), news signal severity, and independent judgment confidence. Include one or two cold-score references only when `crs` data exists. See `references/output-contract.md` § Upset Radar.

10. **Write historical conclusion.** Write a short "过往数据结论" section that explains how historical form/results/stats influence the selected references, while labeling the historical data as context in the bottom source section.

11. **Validate and finalize.** Run the pre-final hook:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/ --final-answer work/world-cup-predictor/YYYYMMDD-HHMM/final.md
```

If no `final.md` draft exists, run the hook without `--final-answer` and manually verify the final line. Fix any hook errors before finalizing. Then run the final quality gate in `references/output-contract.md`, including the required final line `# 仅供娱乐参考`.

## Hard Stops

Stop or narrow the answer when:

- teams, kickoff time, or competition cannot be verified,
- schedule and Sporttery sources refer to different matches,
- a broad "today" request cannot be tied to a US fixture date,
- latest Sporttery multipliers are unavailable for the requested 竞彩 pool,
- Sporttery match identity cannot be matched to the fixture being analyzed,
- player-specific markets are requested but player availability cannot be verified,
- source evidence conflicts and no reliable tie-breaker is available.
- the pre-final hook reports errors.

In these cases, report the data gap and avoid unsupported recommendations.

## Guidance

- Prefer official competition/federation sources for fixtures, Sporttery for 竞彩 multipliers, and official or reputable lineup/injury sources for availability.
- For World Cup requests in the United States, use US/Eastern date as the canonical "today" unless the user specifies another US timezone; keep Sporttery `businessDate` aligned to that US fixture date.
- For performance/context analysis, prioritize current-year World Cup data from the current tournament over older national-team history or generic reputation.
- Treat Polymarket, exchange prices, and overseas sportsbooks as auxiliary context only unless the user explicitly asks for those markets instead of 竞彩.
- Keep player evidence to names, status, role, and only the few metrics needed for the market.
- Treat FBref and official historical results as historical context sources; for national teams, verify that data maps to the actual squad.
- Historical context should influence confidence and reasoning, but it must not replace current Sporttery multipliers, current fixtures, or current availability.
- Use "参考" language. Avoid guaranteed-result wording and staking advice.
- End every final answer with the exact Markdown line `# 仅供娱乐参考`.

## Final Answer Shape

Use Chinese by default. The final answer should be concise, beginner-friendly, source-aware, and structured enough to audit. Keep the body source-neutral and put all source details at the bottom:

```markdown
**数据时间**
...

**今日小白速览**
| 比赛 | 主方向 | 比分参考 | 总进球 | 爆冷雷达 | 信心 |
|---|---|---|---|---|---|

**单场卡片**
### <场次> <主队> vs <客队>
- 赛事判断：
- 胜平负参考：
- 让球参考：
- 比分参考：
- 总进球参考：
- 爆冷雷达：
- 信心指数：

**球队实力画像** (data-sparse matches only)
| 指标 | 主队 | 客队 |
|---|---|---|

**综合推荐**
- 稳胆：
- 价值：
- 防冷：
- 关注：

**逐项理由**
...

**风险提示**
...

**数据来源**
| 用途 | 来源 | 时间 | 说明 |
|---|---|---|---|

# 仅供娱乐参考
```
