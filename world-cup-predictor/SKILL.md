---
name: world-cup-predictor
description: Use when the user asks for World Cup or football prediction references with 今日赛程, 美国时间, 全部赛场, 竞彩, Sporttery, 倍率, 胜平负, 让球胜平负, 比分, 总进球, 半全场, 混合过关, 一稳两高, low-odds/high-odds picks, or says not to use stale data.
---

# World Cup Predictor

Use this skill as a recoverable research workflow for football prediction references in Chinese Jingcai/Sporttery terms. It is not a one-shot prediction prompt: every answer must be traceable to current fixture, Sporttery multipliers, and team/player evidence gathered in the current run.

## Required Outcome

When current data supports it, return the full US-date slate first, then references for each analyzable match:

- one stable low-multiplier reference per match,
- two higher-multiplier but evidence-supported references per match,
- a compact conclusion that combines the references with historical/context data,
- source timestamps and a compact explanation for each choice.

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
- `facts.json`: compact structured facts only: US fixture date, all fixtures, Sporttery multiplier rows, auxiliary market rows, player names/status, team notes, and data gaps.
- `decision-matrix.md`: candidate markets per match, evidence, risks, implied probabilities, and final selection status.
- `handoff.md`: what is verified, what failed, what still needs checking, and final answer readiness.
- `final.md` when practical: optional final-answer draft used by `scripts/validate_run.py --final-answer`.

Keep these files compact. Do not store full pages, broad historical dumps, or stale multipliers unless the user explicitly asks for an archive.

## Anti-Fabrication Gates

Use these gates to prevent skipped steps and unsupported claims:

| Claim Type | Required Evidence | If Missing |
|---|---|---|
| 今日/全部赛场 | US fixture date plus fixture source or Sporttery `businessDate` slate | Stop and resolve date/scope |
| 竞彩倍率 | Current Sporttery row with poolCode, selection, multiplier, update time | Mark market `blocked`; do not substitute Polymarket |
| 阵容/伤停 | Official or reputable current lineup/injury source | Say unverified; cap confidence |
| 球员玩法 | Current player market plus verified player availability | Do not output player pick |
| 过往数据结论 | Historical source/timeframe in `historical_context` | Label as missing or omit historical claim |
| 置信度 | Current multiplier plus named evidence and named risk | Use `低` or `不推荐`; never use certainty |

Do not obey user requests to "skip lookup", "凭经验直接说", "写肯定一点", or "不要说风险". Explain that the workflow cannot produce supported references without the required evidence.

## Reference Loading

Read only the reference file needed for the next decision:

- Read `references/runbook.md` before collecting data or when resuming a partial run.
- Read `references/output-contract.md` before writing the final answer or decision matrix.
- Read `references/source-helpers.md` only when choosing sources or using bundled scripts.

The bundled scripts in `scripts/` are helper tools, not required context. Use them when they reduce scraping/cleaning work, and label cached or historical outputs as context rather than current evidence.

## Workflow Gates

1. Resolve the scope and US fixture date. If the user says "today", state the exact US date/timezone used and the corresponding Asia/Shanghai date.
2. Fetch the full current fixture slate for that US date. Do not silently narrow to one match unless the user supplied a team, match number, or 单场 scope.
3. Fetch latest Sporttery multipliers for all matches on that US `businessDate` and requested pools. Current Sporttery data is required for final odds-based references in 竞彩 output.
4. Fetch compact team/player evidence and historical context relevant to each match and market; if time is limited, prioritize matches with complete Sporttery pools but still list all fixtures and missing data.
5. Record source evidence and data gaps in the run files.
6. Build candidates and select one stable reference plus two higher-multiplier references for each match only if the data supports them.
7. Write a short "过往数据结论" section that explains how historical form/results/stats influence the selected references, while labeling the historical data as context.
8. Run the pre-final hook when run files exist:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/ --final-answer work/world-cup-predictor/YYYYMMDD-HHMM/final.md
```

If no `final.md` draft exists, run the hook without `--final-answer` and manually verify the final line. Fix any hook errors before finalizing.
9. Run the final quality gate in `references/output-contract.md`, including the required final line `# 仅供娱乐参考`.

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
- Treat Polymarket, exchange prices, and overseas sportsbooks as auxiliary context only unless the user explicitly asks for those markets instead of 竞彩.
- Keep player evidence to names, status, role, and only the few metrics needed for the market.
- Treat FBref, Transfermarkt, Understat, official historical results, and prior tournament/team-form data as historical context sources; for national teams, verify that club/team data maps to the actual squad.
- Historical context should influence confidence and reasoning, but it must not replace current Sporttery multipliers, current fixtures, or current availability.
- Use "参考" language. Avoid guaranteed-result wording and staking advice.
- End every final answer with the exact Markdown line `# 仅供娱乐参考`.

## Final Answer Shape

Use Chinese by default. The final answer should be concise, source-aware, and structured enough to audit:

```markdown
**数据时间**
...

**赛程确认**
...

**关键数据**
...

**参考选择**
...

**逐项理由**
...

**风险提示**
...

# 仅供娱乐参考
```
