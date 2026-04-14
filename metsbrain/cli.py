"""Command-line entry point. ``python -m metsbrain <cmd>``"""

from __future__ import annotations

import argparse
import sys

from . import bankroll as br
from . import data
from .advisor import recommend
from .config import AppPaths


def _fmt_pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _fmt_odds(o: int) -> str:
    return f"+{o}" if o > 0 else str(o)


# --- Commands ----------------------------------------------------------------

def cmd_init(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    state.bankroll = args.bankroll
    state.weekly_goal = args.weekly_goal
    state.risk_tolerance = args.risk
    state.ensure_week()
    br.save(state, paths.state_file)
    print(
        f"Initialized. Bankroll=${state.bankroll:.2f} "
        f"Weekly goal=${state.weekly_goal:.2f} Risk={state.risk_tolerance}"
    )
    return 0


def cmd_advise(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    if state.bankroll <= 0:
        print("Bankroll is 0. Run `python -m metsbrain init` first.", file=sys.stderr)
        return 2

    provider = data.SampleDataProvider()
    games = provider.upcoming_games()

    recs = recommend(
        games,
        bankroll=state.bankroll,
        weekly_goal=state.weekly_goal,
        week_profit=state.week_profit(),
        days_remaining=state.days_remaining_in_week(),
        risk_tolerance=state.risk_tolerance,
    )

    if not recs:
        print("No +EV plays found this slate at your risk tolerance. Sit on your wallet.")
        return 0

    print(f"{'GAME':28} {'MARKET':14} {'SIDE':6} {'ODDS':>6} "
          f"{'MODEL':>6} {'IMPLIED':>7} {'EDGE':>6} {'KELLY':>6} {'RISK':6} {'STAKE':>8}")
    print("-" * 110)
    for r in recs:
        line = f" ({r.line:+})" if r.line is not None else ""
        print(
            f"{r.game_id:28} {r.market+line:14} {r.side:6} "
            f"{_fmt_odds(r.american_odds):>6} "
            f"{_fmt_pct(r.model_prob):>6} {_fmt_pct(r.implied_prob):>7} "
            f"{_fmt_pct(r.edge):>6} {_fmt_pct(r.kelly_full):>6} "
            f"{r.risk_bucket:6} ${r.stake:7.2f}"
        )
        for note in r.rationale:
            print(f"    why: {note}")
        print()

    return 0


def cmd_log_bet(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    bet = br.log_bet(
        state,
        game_id=args.game,
        market=args.market,
        side=args.side,
        american_odds=args.odds,
        stake=args.stake,
    )
    br.save(state, paths.state_file)
    print(f"Logged bet #{bet.id}: {bet.stake:.2f} on {bet.side} {bet.market} @ {_fmt_odds(bet.american_odds)}")
    return 0


def cmd_settle(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    bet = br.settle_bet(state, args.id, args.result)
    br.save(state, paths.state_file)
    print(
        f"Settled #{bet.id} as {bet.result}. "
        f"Payout ${bet.payout:+.2f}. New bankroll: ${state.bankroll:.2f}"
    )
    return 0


def cmd_week(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    profit = state.week_profit()
    goal = state.weekly_goal
    pct = (profit / goal * 100.0) if goal else 0.0
    print(f"Week of {state.week_anchor}")
    print(f"  Bankroll:     ${state.bankroll:.2f}")
    print(f"  Weekly goal:  ${goal:.2f}")
    print(f"  Week profit:  ${profit:+.2f} ({pct:+.1f}% of goal)")
    print(f"  Days left:    {state.days_remaining_in_week()}")
    print(f"  Risk on open: ${state.open_risk():.2f}")
    open_bets = [b for b in state.bets if b.result == "open"]
    if open_bets:
        print("  Open bets:")
        for b in open_bets:
            print(f"    #{b.id} {b.game_id} {b.side} {b.market} @ {_fmt_odds(b.american_odds)} for ${b.stake:.2f}")
    return 0


def cmd_status(args, paths: AppPaths) -> int:
    state = br.load(paths.state_file)
    print(
        f"Bankroll=${state.bankroll:.2f} "
        f"Goal=${state.weekly_goal:.2f} "
        f"Risk={state.risk_tolerance} "
        f"Bets logged={len(state.bets)}"
    )
    return 0


# --- Arg parsing -------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metsbrain", description="Mets-only betting advisor")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="Set bankroll, weekly goal, risk tolerance")
    pi.add_argument("--bankroll", type=float, required=True)
    pi.add_argument("--weekly-goal", type=float, required=True)
    pi.add_argument("--risk", choices=["low", "medium", "high"], default="medium")
    pi.set_defaults(func=cmd_init)

    pa = sub.add_parser("advise", help="Print recommended bets for upcoming Mets games")
    pa.set_defaults(func=cmd_advise)

    pl = sub.add_parser("log-bet", help="Log a bet you placed")
    pl.add_argument("--game", required=True)
    pl.add_argument("--market", required=True)
    pl.add_argument("--side", required=True)
    pl.add_argument("--odds", type=int, required=True)
    pl.add_argument("--stake", type=float, required=True)
    pl.set_defaults(func=cmd_log_bet)

    ps = sub.add_parser("settle", help="Settle a logged bet")
    ps.add_argument("--id", type=int, required=True)
    ps.add_argument("--result", choices=["win", "loss", "push"], required=True)
    ps.set_defaults(func=cmd_settle)

    pw = sub.add_parser("week", help="Show weekly pace, goal progress, open bets")
    pw.set_defaults(func=cmd_week)

    pt = sub.add_parser("status", help="One-line status summary")
    pt.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = AppPaths()
    return args.func(args, paths)


if __name__ == "__main__":
    raise SystemExit(main())
