# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Metsbrain is a single-user, local-first **Mets-only sports-betting advisor**.
It does not place bets. It takes a bankroll, a weekly revenue goal, and a
risk tolerance, then surfaces ranked +EV Mets plays with fractional-Kelly
stake sizes bent around weekly-goal pace.

**Always read `DESIGN.md` before making non-trivial changes.** It is the
source-of-truth for scope, locked decisions, data model, bet-sizing rules,
and the phased roadmap. The codebase is implemented *against* that doc.

## Development branch

All work on this project ships on `claude/mets-betting-advisor-IARCq`.
Never push to `main` or any other branch without explicit permission.

## Commands

```bash
# install deps (runtime + test)
pip install -r requirements.txt

# initialize local state — creates ./.metsbrain.db (SQLite)
python -m metsbrain init --bankroll 1000 --weekly-goal 150 --risk medium

# CLI surface
python -m metsbrain advise           # top-3 Mets picks per day with rationale
python -m metsbrain log-bet --game <id> --market <m> --side <s> --odds <n> --stake <n>
python -m metsbrain settle --id <n> --result {win,loss,push}
python -m metsbrain week             # pace report + open bets
python -m metsbrain status
python -m metsbrain serve            # FastAPI web UI on 127.0.0.1:8765

# tests (stdlib + pytest)
python -m pytest tests/ -q                     # full suite
python -m pytest tests/test_advisor.py -q      # one file
python -m pytest tests/test_advisor.py::test_goal_hit_triggers_lockdown -q  # one test
```

There is no lint or build step. The project is pure Python (stdlib + four
runtime deps: fastapi, jinja2, uvicorn, python-multipart).

## Architecture — the big picture

Strict layering. Each arrow flows downward; nothing above calls laterally.

```
CLI (cli.py)   ←→   Web UI (web.py + templates/)
           \            /
            \          /
             Service (service.py)      ← only layer that touches Store + DataProvider
            /    |    \
           /     |     \
      Advisor Analysis Props           ← pure functions, no I/O
         |        (+sizing, odds)
         v
       Models (dataclasses)
         |
         v
       Store (store.py, SQLite)
```

- `metsbrain/models.py` — all dataclasses (`Game`, `OfferedLine`,
  `Recommendation`, `LoggedBet`, `PitcherLine`, `BatterProfile`, etc.). No
  behavior, just shapes.
- `metsbrain/config.py` — every tunable lives here: model weights, Kelly
  fraction, risk tiers, edge thresholds, max bets/day, correlation cap,
  drawdown cool-down %. Change behavior here first before changing logic.
- `metsbrain/odds.py` — American↔decimal, implied prob, Kelly. Pure math.
- `metsbrain/analysis.py` — heuristic weighted-logistic model producing
  `p_win`, `p_over`, `p_f5_win`, and per-feature contributions for rationale.
- `metsbrain/props.py` — prob functions for HR (binomial over PAs), hits
  over N (binomial over ABs), SP Ks over N (Poisson). Each returns a
  rationale list.
- `metsbrain/sizing.py` — fractional Kelly + `pace_factor` modulated by
  weekly-goal progress; honors `pace_factor_override` for lockdown.
- `metsbrain/advisor.py` — `recommend()` is the real entry point. Applies
  (in order): **weekly-drawdown cool-down** (>25% → no picks),
  **goal-hit lockdown** (profit ≥ goal → low-risk only, 0.5× pace),
  per-game **correlation cap** (7% of bankroll), edge-sorted
  **max-3-per-day** cap. Changing any rule here without updating DESIGN.md
  is a smell.
- `metsbrain/data.py` — `DataProvider` Protocol + `SampleDataProvider`
  (bundled realistic-looking slate for offline dev). Real MLB data lands
  behind this seam in Phase 3; don't add network calls elsewhere.
- `metsbrain/store.py` — SQLite (stdlib `sqlite3`, no ORM). Six tables
  from DESIGN.md §4: `app_meta`, `weeks`, `games`, `feature_snapshots`,
  `offered_lines`, `recommendations`, `bets`. Upserts for offered_lines
  are NULL-safe via `IFNULL(...)` comparisons so prop keys work.
- `metsbrain/service.py` — high-level operations (`init_app`, `advise`,
  `log_bet`, `settle_bet`, `enter_odds`, `week_summary`,
  `upcoming_games`). **Both CLI and web drive the app through Service**
  — keep them behaviorally identical. `upcoming_games()` merges DB-stored
  odds overrides on top of the data provider's default lines.
- `metsbrain/web.py` + `templates/` + `static/style.css` — FastAPI with
  server-rendered Jinja (no JS framework). Three pages: Today (`/`),
  Odds (`/enter-odds`), Week (`/week`). Phone-browser-first CSS.

### State & reproducibility

Every `advise` run persists a `feature_snapshot` per game plus every
`recommendation` it surfaces (separate from `bets` — the bets table only
holds what you actually placed). This split lets us later answer *"would
I be up if I'd followed the app verbatim?"* Do not collapse that separation.

### Locked design decisions (from DESIGN.md §2)

Do not change without asking:

1. Goal-hit mid-week → low-risk only + 0.5× Kelly until next Monday.
2. Max 3 bets/day.
3. Risk tolerance is static (set at `init`, never shifts mid-week).
4. Props (HR / hits / SP Ks) supported in v1.
5. Odds are **manually entered** (no paid odds API wiring in scope).
6. Persistence is SQLite.
7. No parlays.
8. Web UI is a peer of the CLI, not Phase-5 material.

## Conventions that matter here

- **Never bypass `Service`.** CLI / web / tests all construct a `Service`
  and call its methods. Don't reach into `Store` from a handler; add a
  service method.
- **Never add network I/O outside `data.py`.** That's the seam. The
  advisor, analysis, props, and sizing modules must stay pure-functional.
- **Tunables go in `config.py`,** not inline in logic modules. If you
  find yourself hardcoding a threshold, move it.
- **Tests are the contract for advisor rules.** `tests/test_advisor.py`
  has specific tests for lockdown, correlation cap, max-3, drawdown
  cool-down, and the prop pathway. If you change those rules, update the
  tests in the same commit.
- **Sample data is a fixture, not a demo.** `SampleDataProvider` is used
  by both the app and several tests. Changing its numbers will ripple
  through advisor tests — do that deliberately, not as a drive-by.

## Phased roadmap (current: Phase 2 complete)

1. ✅ Skeleton refactor — layered architecture, SQLite, props, advisor rules.
2. ✅ Local web UI — FastAPI + server-rendered HTML, manual odds flow.
3. ⬜ Real Mets data — MLB Stats API + Open-Meteo + pybaseball behind `DataProvider`.
4. ⬜ Backtest + calibration — replay past seasons, tune weights, calibrate probs.
5. ⬜ Weekly review dashboard — ROI by market, CLV tracking.
6. ⬜ (maybe) Live/in-game adjustments.
