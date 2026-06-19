# Output Contract

Read this before writing the final answer or finalizing `decision-matrix.md`.

## Final Quality Gate

Every odds-based final answer must satisfy these checks:

- Exact match identity is verified: teams, competition, date, kickoff time, timezone.
- For broad "today" requests, the answer covers every fixture on the US fixture date; it does not choose only the easiest or most data-complete match.
- For 竞彩/Sporttery requests, the final multiplier source is Sporttery and the poolCode is named.
- Polymarket or overseas odds are labeled as auxiliary context only and are not used as the final 竞彩倍率.
- Each selected reference has 竞彩玩法, poolCode, selection, current Sporttery multiplier, implied probability, and confidence.
- Player-specific reasoning uses verified player availability or explicitly says availability is unverified.
- The answer includes a compact historical-data conclusion section that explains how past form/results/stats affect the final references.
- Historical data is labeled as context with a source/timeframe or explicit "historical context" label; it cannot replace current Sporttery multipliers, current fixtures, or current availability.
- Missing data is named and reflected in confidence or market exclusion.
- Run files pass `scripts/validate_run.py` before finalization when a run folder exists. If a final draft file exists, pass it with `--final-answer` so the disclaimer is machine-checked.
- The answer uses "参考" framing and avoids guaranteed-result language.
- The final line of the answer is exactly `# 仅供娱乐参考`.

If any check fails, revise the answer or mark the affected market `blocked`.

## Pre-Final Hook

Run this before finalizing whenever the workflow created run files:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/
```

If a draft final answer is saved:

```bash
python3 scripts/validate_run.py work/world-cup-predictor/YYYYMMDD-HHMM/ --final-answer work/world-cup-predictor/YYYYMMDD-HHMM/final.md
```

Do not ignore hook errors. A warning may be disclosed as a data limitation; an error must be fixed or the affected recommendation must be blocked before final output.

## Recommendation Rules

Return three references only when data supports all three:

| Type | Required Evidence | Typical Confidence |
|---|---|---|
| Stable low multiplier | current Sporttery multiplier plus fixture plus basic team/availability check | 中 or 中高 |
| Higher multiplier 1 | current Sporttery multiplier plus market-specific team/player evidence | 中 or lower |
| Higher multiplier 2 | different Sporttery pool from high 1 plus evidence | 中 or lower |

Do not force a player scorer, exact score, cards, or corners pick without market-specific evidence. For exact score, use `crs` only when Sporttery returns current prices for that match.

For all-slate mode, apply the three-reference rule per match. If a match lacks a pool, keep the match in the schedule and mark the affected reference `blocked` or replace it with another Sporttery pool only when evidence supports that replacement.

## Confidence Labels

- `中高`: current Sporttery multiplier, fixture, availability, and relevant evidence align.
- `中`: Sporttery multiplier and fixture are current, but lineup or player evidence has ordinary uncertainty.
- `低`: data exists but conflicts, market is volatile, or key evidence is weak.
- `不推荐`: data gap or price makes the market unsuitable.

## Report Template

Use Chinese unless the user requests another language:

```markdown
**数据时间**
- 当前日期/时区：
- 美国赛事日：
- 赛程来源：
- Sporttery 倍率来源与抓取时间：
- 辅助市场来源：

**美国时间赛程确认**
| 场次 | 比赛 | 美国时间 | 上海时间 | 赛事 | Sporttery状态 |
|---|---|---:|---:|---|---|

**关键数据**
- 阵容/伤停：
- 球队近况：
- Sporttery 倍率/玩法：
- 辅助市场：
- 数据缺口：

**过往数据结论**
| 比赛 | 过往数据/历史背景 | 对参考的影响 | 数据限制 |
|---|---|---|---|
| ... | ... | ... | ... |

**参考选择**
| 比赛 | 类型 | 竞彩玩法 | poolCode | 选择 | Sporttery 倍率 | 隐含概率 | 置信度 |
|---|---|---|---|---|---:|---:|---|
| ... | 稳定低倍率 | ... | ... | ... | ... | ... | ... |
| ... | 高倍率参考 1 | ... | ... | ... | ... | ... | ... |
| ... | 高倍率参考 2 | ... | ... | ... | ... | ... | ... |

**逐项理由**
1. 稳定低倍率：
2. 高倍率参考 1：
3. 高倍率参考 2：

**风险提示**
- ...

# 仅供娱乐参考
```

If fewer than three references are valid, keep the table rows that are valid and add a short "未输出原因" line. If Sporttery data is missing, say "Sporttery 未返回该玩法/比赛，未用 Polymarket 替代".

The final disclaimer must remain the last line. Do not put any text, sources, or sign-off after `# 仅供娱乐参考`.

## Implied Probability

Use decimal Sporttery multipliers:

```text
implied_probability = 1 / multiplier
```

For complete markets such as 1X2, optionally normalize bookmaker margin when all outcomes are available. If not all outcomes are available, do not imply precision; state that the probability is raw implied probability.
