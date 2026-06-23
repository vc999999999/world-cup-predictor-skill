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
- Each match with a data-sparse team (FIFA rank 80+ or EA FC OVR < 68) includes a `球队实力画像` mini-card showing FIFA ranking, EA FC ratings, and strength tier.
- The `爆冷雷达` incorporates EA FC rating differential and odds movement signals in addition to exact-score prices and handicap direction.
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

### Enhanced Upset Signals (Weak-Team Matches)

In addition to exact-score prices and handicap direction, incorporate these signals:

| Signal | Trigger | Effect on 爆冷雷达 |
|---|---|---|
| EA FC rating gap < 5 | Two teams with similar OVR ratings | Increase upset probability; teams closer than ranking suggests |
| FIFA ranking gap > 40 but tight odds | Strong team not priced as strong | Flag as 中 or 高; market disagrees with ranking |
| Odds drift toward weak team | Significant movement (7%+) shortening weak team's win price | Increase upset radar; possible insider info |
| H2H weak-team edge | Underdog has winning H2H record | Mention as psychological factor |
| Conflicting signals | EA FC says strong, odds say close | Upgrade to 中 or 高 depending on other evidence |
| Core player star factor | Data-sparse team has elite star (OVR >= 85) while opponent does not | Mention as X-factor; can increase upset probability if star is match-decisive |
| External news signal | High-severity injury/suspension to key player on either team (from BBC RSS) | Downgrade confidence if elite star affected; upgrade if rival's key player is out |

## Core Player Upset Signals

When `references/core-players.json` shows an elite (OVR >= 85) or star (OVR >= 83) player for a data-sparse team, incorporate this as a `核心球星因素` in the upset radar:

| Scenario | Effect on 爆冷雷达 | Example |
|---|---|---|
| Data-sparse team has elite star; opponent has none | Increase upset probability if star is in attack/midfield and in form | South Korea with Son Heung-min vs a mid-tier team without stars |
| Both teams have elite stars | Neutral; treat as normal match | Argentina vs Brazil (both have multiple elite stars) |
| Favorite has elite star; underdog does not | Standard analysis; star factor does not change radar | France with Mbappé vs data-sparse team without stars |
| Elite star injured/ruled out (from news signals) | Downgrade that team's capability | If core_players.json lists a star but news_signals shows injury |

Record the matched players in `facts.json.core_players` and cross-check `facts.json.news_signals` for any injury or suspension affecting them.

## Team Strength Profile Card

For each match involving a data-sparse team, include a compact strength profile:

```markdown
**球队实力画像** — <主队> vs <客队>
| 指标 | 主队 | 客队 |
|---|---|---|
| FIFA 排名 | 52 (1423.5分) | 87 (1201.0分) |
| EA FC 评分 | OVR 71 / ATT 68 / MID 72 / DEF 73 | OVR 63 / ATT 60 / MID 65 / DEF 64 |
| 实力档次 | 中下 | 弱 |
| H2H 趋势 | 主队略优 (近5场 W3 D1 L1) | |
| 赔率变动 | 主胜赔率 ↓0.08 (偏向主队) | |
```

This card helps beginners understand WHY a weak team might over- or under-perform expectations.

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

**球队实力画像** (for data-sparse matches)
| 指标 | 主队 | 客队 |
|---|---|---|
| FIFA 排名 | ... | ... |
| EA FC 评分 | ... | ... |
| 实力档次 | ... | ... |
| H2H 趋势 | ... | ... |
| 赔率变动 | ... | ... |

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
