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
- The body is beginner-friendly: it starts with `今日小白速览`, then uses one compact `单场卡片` per match, then `综合推荐`.
- The body does not contain source names, URLs, retrieval notes, or inline citations. Use source-neutral labels such as `当前赛程`, `当前竞彩倍率`, `阵容信息`, and `历史背景`.
- A bottom `数据来源` section appears immediately before the final disclaimer and contains all source names, URLs, retrieval times, and current/context labels.
- Each match has a `爆冷雷达` value: `低`, `中`, `高`, or `数据不足`. If exact-score (`crs`) data exists, include the main cold-score reference; if it does not, say score data is unavailable instead of inventing a cold score.
- The answer includes a compact historical-data conclusion section that explains how past form/results/stats affect the final references.
- Historical data is labeled as context in the bottom source section with a source/timeframe or explicit "historical context" label; it cannot replace current Sporttery multipliers, current fixtures, or current availability.
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

## Upset Radar

Add `爆冷雷达` for every match:

| Label | Use When | Output |
|---|---|---|
| `低` | Favorite direction, handicap, exact-score prices, and team evidence mostly align | Say major upset is not the main route; list only routine score references |
| `中` | Favorite still leads, but draw/underdog score prices or team evidence show a live cold route | Name the cold route, such as `防平` or `防客胜`, plus one cold-score reference if `crs` exists |
| `高` | Market shape and football evidence both show favorite fragility or underdog strength | Warn clearly, downgrade confidence, and avoid overly bold stable picks |
| `数据不足` | Exact-score market or key evidence is missing | Do not invent a cold score; explain the missing score evidence |

Treat a "major upset" as an underdog win, a heavy favorite failing to win, or a handicap result that strongly contradicts the main direction. Do not call something a major upset only because the exact-score multiplier is high; it needs football evidence plus market shape.

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
- 数据口径：
- 数据完整度：

**今日小白速览**
| 场次 | 比赛 | 主方向 | 比分参考 | 总进球 | 爆冷雷达 | 信心 |
|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... |

**单场卡片**
### <场次> <主队> vs <客队>
- 赛事判断：
- 胜平负参考：
- 让球参考：
- 比分参考：
- 总进球参考：
- 爆冷雷达：
- 信心指数：
- 小白备注：

**过往数据结论**
| 比赛 | 历史背景 | 对参考的影响 | 数据限制 |
|---|---|---|---|
| ... | ... | ... | ... |

**参考选择**
| 比赛 | 类型 | 竞彩玩法 | poolCode | 选择 | 当前倍率 | 隐含概率 | 置信度 |
|---|---|---|---|---|---:|---:|---|
| ... | 稳定低倍率 | ... | ... | ... | ... | ... | ... |
| ... | 高倍率参考 1 | ... | ... | ... | ... | ... | ... |
| ... | 高倍率参考 2 | ... | ... | ... | ... | ... | ... |

**综合推荐**
- 稳胆：
- 价值：
- 防冷：
- 关注：

**逐项理由**
1. 稳定低倍率：
2. 高倍率参考 1：
3. 高倍率参考 2：

**风险提示**
- ...

**数据来源**
| 用途 | 来源 | 时间 | 类型 | 说明 |
|---|---|---|---|---|
| 赛程/比赛身份 | ... | ... | current | ... |
| 竞彩倍率 | ... | ... | current | ... |
| 阵容/伤停 | ... | ... | current/context | ... |
| 历史背景 | ... | ... | context | ... |

# 仅供娱乐参考
```

If fewer than three references are valid, keep the table rows that are valid and add a short "未输出原因" line. If current 竞彩 data is missing, say "当前竞彩数据未返回该玩法/比赛；未用辅助市场替代".

The final disclaimer must remain the last line. Do not put any text, sources, or sign-off after `# 仅供娱乐参考`.

## Implied Probability

Use decimal Sporttery multipliers:

```text
implied_probability = 1 / multiplier
```

For complete markets such as 1X2, optionally normalize bookmaker margin when all outcomes are available. If not all outcomes are available, do not imply precision; state that the probability is raw implied probability.
