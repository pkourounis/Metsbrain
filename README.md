# Metsbrain

A personal sports-betting **advisor** for New York Mets games. It does not
place bets. It tells you:

1. Which upcoming Mets bets look like +EV based on a Mets-specific feature
   model.
2. How much to stake on each one, sized with fractional Kelly and bent around
   your **weekly revenue goal** and risk tolerance.
3. How your week is pacing so you can stop chasing or ease off when ahead.

## Quick start

```bash
pip install -r requirements.txt

# one-time: set bankroll + weekly goal + risk tolerance
python -m metsbrain init --bankroll 1000 --weekly-goal 150 --risk medium

# local web UI (phone browser friendly) → http://127.0.0.1:8765
python -m metsbrain serve

# or use the CLI directly
python -m metsbrain advise
python -m metsbrain log-bet --game NYM-vs-PHI-2026-04-15 --market moneyline --side NYM --odds -120 --stake 22
python -m metsbrain settle --id 3 --result win
python -m metsbrain week
```

State lives in a local `.metsbrain.db` SQLite file. Single user, no network
access required, nothing leaves your machine.

## How bets are evaluated

For each upcoming Mets game, Metsbrain builds a feature vector:

- Starting pitcher ERA / FIP / WHIP differential, including recent form
- Bullpen ERA and rest
- Team wRC+ / OPS vs opponent handedness (last 14 days)
- Home / away + Citi Field park factor
- Injuries to key players (Lindor, Alonso, Nimmo, Diaz, ace SP)
- Weather for home games (wind out to RF boosts totals)
- Rest / travel
- Opponent run environment

These are combined with tunable weights into:

- `p_win` — model probability the Mets win
- `p_total_over` — model probability the total goes over
- `p_f5_win` — model probability Mets lead after 5

For every offered market, model probability is compared against the
sportsbook's implied probability (devigged). If there is a positive edge, the
bet is surfaced with an edge %, Kelly %, recommended stake, and a risk bucket.

## Bet sizing

Base stake = `kelly_fraction * kelly_optimal * bankroll`

- `kelly_fraction` defaults to 0.25 (quarter Kelly).
- It is multiplied by a **pace factor** driven by weekly-goal progress:
  - Behind pace → up to 1.5x (capped)
  - Ahead of goal → 0.5x
- And by a **risk factor**:
  - `low` → 0.5x and only low-risk buckets are surfaced
  - `medium` → 1.0x
  - `high` → 1.5x and high-risk plays are surfaced

Max single-bet stake is capped at 5% of bankroll regardless.

## Scope

This ships with a sample data provider so it runs without network access.
Hook a real feed (MLB Stats API, pybaseball, an odds API) into
`metsbrain/data.py::DataProvider` when you are ready.
