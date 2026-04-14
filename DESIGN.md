# Metsbrain — Design

A personal, single-user sports betting **advisor** for New York Mets games.
Advises on bets; never places them. Helps you reach a weekly revenue goal
without blowing up your bankroll.

## 1. Goals & non-goals

**Goals**
- Advise on bets for New York Mets games only. Everything else is context.
- Given a **bankroll**, **weekly revenue goal**, and **risk tolerance**, output:
  - A ranked list of +EV bets for today's Mets slate (max 3).
  - A recommended stake on each, sized to pace toward the weekly goal.
  - Enough rationale to audit every pick.
- Track P&L so pace awareness is accurate and future picks adjust accordingly.

**Non-goals**
- Does not place bets or hold sportsbook credentials.
- Not a general MLB model. Mets-specificity is a feature, not a limitation.
- Not multi-user, not shared, not cloud-hosted. Local-first.
- No parlays.

## 2. Locked decisions

| # | Decision | Answer |
|---|---|---|
| 1 | Behavior at weekly goal mid-week | Low-risk bucket only, 0.5x Kelly until next Monday |
| 2 | Max bets per day | 3 |
| 3 | Risk tolerance | Static — set at `init`, never shifts during the week |
| 4 | Props | In v1 (HR / hits for Lindor, Alonso, Nimmo; SP Ks over N) |
| 5 | Odds source | Manual entry |
| 6 | Persistence | SQLite (single local `metsbrain.db` file) |
| 7 | Parlays | Not supported |
| 8 | Interface | CLI first, **local web UI brought forward** (phone-browser friendly) |

## 3. Architecture

```
+------------------------------------------------------+
|  Interface:  CLI  +  FastAPI web UI (same backend)   |
+------------------------------------------------------+
|  Advisor:    ranking, sizing, pace, caps, lockdowns  |
+------------------------------------------------------+
|  Models:     win / total / F5 / prop prob functions  |
+------------------------------------------------------+
|  Features:   extractors over normalized data         |
+------------------------------------------------------+
|  Data:       MLB Stats API, Open-Meteo, manual odds  |
|              (+ local cache of every fetch)          |
+------------------------------------------------------+
|  Store:      SQLite; tables below                    |
+------------------------------------------------------+
```

Principle: **every recommendation is reproducible.** When we advise, we snapshot
every input used. When a bet settles, we can retroactively score the model.

## 4. Data model (SQLite tables)

- `weeks` — week anchor (Monday ISO), starting bankroll, goal, risk tolerance,
  ending bankroll when week closes.
- `games` — Mets game row: date, opponent, home/away, mets SP id, opp SP id.
- `feature_snapshots` — JSON blob of feature vector + timestamp + game_id.
  One row per `advise` run for a given game.
- `offered_lines` — market, side, player (nullable), threshold (nullable),
  american odds, line (nullable), game_id, entered_at.
- `recommendations` — what the advisor said to do. Captured independent of
  whether you placed the bet. Columns: game_id, market, side, player,
  threshold, american odds, model_prob, edge, kelly_full, stake, risk_bucket,
  rationale (JSON), advised_at.
- `bets` — what you actually placed. Columns: recommendation_id (nullable —
  you might bet off-advisor), game_id, market, side, player, threshold,
  stake, american odds, placed_at, result (open/win/loss/push), payout,
  settled_at.

Separating `recommendations` from `bets` is how we answer
"would I be up if I'd followed the app verbatim?"

## 5. Markets supported (v1)

- `moneyline` (NYM / OPP)
- `run_line` +/- 1.5 (NYM / OPP)
- `total_over`, `total_under`
- `f5_moneyline` (NYM / OPP)
- `prop_hr` — HR yes/no for Lindor, Alonso, Nimmo
- `prop_hits_over` — over/under 0.5 or 1.5 hits for Lindor, Alonso, Nimmo
- `prop_sp_ks_over` — over N strikeouts for Mets starting pitcher

No parlays, no alt lines beyond these, no live/in-game lines.

## 6. The model

v1 is a **transparent weighted-logistic model**: standardized feature deltas,
hand-tuned weights, logistic squash. Every probability comes with a feature-
contribution vector so rationale is automatic.

v2 is a trained classifier — **only after** we have a backtest harness and a
full season of snapshots to train and calibrate against. A trained model
without a baseline is a model you cannot trust.

### 6.1 Features

- **Starter matchup**: ERA, FIP, WHIP, K%, BB%, last-3-starts game score,
  times-through-order penalty.
- **Bullpen**: aggregate ERA, last-3-days usage, top-3 reliever availability.
- **Offense**: wRC+ and 14-day OPS, split by opposing-pitcher handedness.
- **Today's lineup**: actual starting 9 (Alonso in vs out is material).
- **Park**: Citi run factor; opposing park on the road.
- **Weather**: wind speed/direction, temperature, precipitation risk (home only).
- **Rest & travel**: days rest, travel distance, series context.
- **Injuries**: weighted by player WAR impact.
- **Umpire** (stretch): strike-zone size.

### 6.2 Outputs per game

- `p_win`, `p_cover(-1.5)`, `p_cover(+1.5)`, `p_over(N)`, `p_under(N)`, `p_f5_win`
- Per-prop probabilities (`p_hr(player)`, `p_hit(player, threshold)`,
  `p_sp_ks_over(N)`)
- Feature-contribution vector for each prediction

### 6.3 Calibration

Run probabilities through Platt scaling or isotonic regression against
historical outcomes so "70%" actually means 70%. Without this, Kelly is
unsafe. Calibration data comes from backtesting (later phase).

## 7. Bet sizing

### 7.1 Fractional Kelly with hard guards

- Base: quarter Kelly (`KELLY_FRACTION_BASE = 0.25`).
- Hard cap: 5% of bankroll per single bet.
- Hard cap: 7% of bankroll across correlated bets on the same game.
- Minimum stake: skip anything under $5 (noise).

### 7.2 Weekly-goal pace factor

`P ∈ [0.5, 1.5]`:

- `expected = weekly_goal * (days_elapsed / 7)`
- `shortfall = expected − week_profit`
- Normalize shortfall by `weekly_goal`, clamp to `[-1, 1]`.
- Behind pace → scale up toward 1.5x; ahead → scale down toward 0.5x.

### 7.3 Goal-hit lockdown

When `week_profit >= weekly_goal`:
- Filter picks to risk bucket `low` only.
- Pace factor forced to `0.5`.
- Stays locked until week rolls to next Monday.

### 7.4 Risk tolerance (static)

| Tier | Size multiplier | Surfaces picks where model prob >= |
|---|---|---|
| low    | 0.5x | 0.60 |
| medium | 1.0x | 0.50 |
| high   | 1.5x | 0.45 (edge must be larger) |

Set once at `init`. Does not change during the week.

### 7.5 Daily cap

After sizing and filtering, the advisor returns **at most 3 picks** per day,
ranked by edge. Correlation cap is enforced before the top-3 selection so we
don't burn all 3 slots on correlated Mets-win plays.

## 8. Data sources

| Need | Source | Cost |
|---|---|---|
| Schedule, lineups, box scores | MLB Stats API | Free |
| Pitcher / team splits | pybaseball | Free, rate-limited |
| Weather at Citi | Open-Meteo | Free |
| Odds | Manual entry via web UI or CLI | Free |

Every fetch goes through a `DataProvider` with local cache keyed by
`(source, endpoint, date)`. Makes dev offline and backtests reproducible.

## 9. Interfaces

### 9.1 CLI

- `init` — set bankroll, goal, risk tier
- `advise [--date]` — today's top-3 Mets plays with rationale
- `explain <game_id>` — deep-dive feature contributions
- `enter-odds <game_id>` — add/update offered lines manually
- `log-bet` — record a placed bet
- `settle` — mark a bet win/loss/push
- `week` — pace + goal + open-risk report
- `status` — one-line summary
- `review --week` — hit rate, ROI by market, CLV when available

### 9.2 Local web UI (FastAPI + server-rendered HTML, no JS framework)

Three pages, phone-browser friendly:

1. **Today** — slate with top-3 picks, stakes, rationale; log-bet buttons.
2. **Enter odds** — form per game/market, saves to DB.
3. **Week** — bankroll, goal progress, open bets, settle buttons, history.

Served at `localhost:8765` by default. No auth (single-user, local-only).

## 10. Safety

- Refuse to surface picks if bankroll dropped > 25% this week (cool-down).
- All randomness seeded.
- All model inputs + outputs logged to `feature_snapshots` and `recommendations`.
- Never prompts for or stores sportsbook credentials.

## 11. Phased roadmap

1. **Phase 1 — Skeleton refactor.** Layered architecture, SQLite, prop markets
   in the data model, max-3 + correlation + goal-lockdown rules in the
   advisor, prototype heuristic model carried over.
2. **Phase 2 — Web UI.** FastAPI + server-rendered HTML for Today / Enter odds
   / Week. Same logic as CLI, shared service layer.
3. **Phase 3 — Real Mets data.** MLB Stats API + Open-Meteo + pybaseball for
   features, with caching. Props powered by real splits.
4. **Phase 4 — Backtest & calibration.** Replay last 1–2 Mets seasons; tune
   weights from data; calibrate probabilities.
5. **Phase 5 — Weekly review dashboard.** Model diagnostics, ROI by market,
   CLV tracking (when you record the closing line).
6. **Phase 6 — Maybe in-game / live.** Only if Phases 1–5 show positive ROI.

## 12. Out of scope (explicit)

- Parlays, teasers, same-game parlays.
- Sports other than MLB.
- Teams other than the Mets.
- Automated order placement at any sportsbook.
- Cloud sync; multi-device state.
- Social features.
