"""Command-line entry point. ``python -m metsbrain <cmd>``

Thin wrapper over Service — everything real lives behind service.py so the
web UI (Phase 2) can share the same behavior.
"""

from __future__ import annotations

import argparse
import sys

from .config import AppPaths
from .service import Service
from .store import Store


def _fmt_pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def _fmt_odds(o: int) -> str:
    return f"+{o}" if o > 0 else str(o)


def _service(paths: AppPaths) -> Service:
    return Service(Store(paths.db_file))


# --- Commands ----------------------------------------------------------------

def cmd_init(args, paths: AppPaths) -> int:
    svc = _service(paths)
    svc.init_app(bankroll=args.bankroll, weekly_goal=args.weekly_goal, risk=args.risk)
    print(
        f"Initialized. Bankroll=${args.bankroll:.2f} "
        f"Weekly goal=${args.weekly_goal:.2f} Risk={args.risk}"
    )
    svc.store.close()
    return 0


def cmd_advise(args, paths: AppPaths) -> int:
    svc = _service(paths)
    if svc.store.get_bankroll() <= 0:
        print("Bankroll is 0. Run `python -m metsbrain init` first.", file=sys.stderr)
        svc.store.close()
        return 2

    recs = svc.advise()

    if not recs:
        wk = svc.week_summary()
        if wk["weekly_goal"] > 0 and wk["week_profit"] >= wk["weekly_goal"]:
            print("Weekly goal already hit. Locked to low-risk only — no picks today.")
        elif wk["starting_bankroll"] > 0 and (
            (wk["starting_bankroll"] - wk["bankroll"]) / wk["starting_bankroll"] > 0.25
        ):
            print("Weekly drawdown > 25%. Cool-down in effect until next Monday.")
        else:
            print("No +EV plays found at your risk tolerance. Sit on your wallet.")
        svc.store.close()
        return 0

    print(f"{'GAME':28} {'MARKET':18} {'SIDE':6} {'ODDS':>6} "
          f"{'MODEL':>6} {'IMPLIED':>7} {'EDGE':>6} {'KELLY':>6} {'RISK':6} {'STAKE':>8}")
    print("-" * 116)
    for r in recs:
        descriptor = r.market
        if r.line is not None:
            descriptor += f" ({r.line:+})"
        if r.player:
            descriptor += f" {r.player}"
        if r.threshold is not None:
            descriptor += f" {r.threshold}"

        print(
            f"{r.game_id:28} {descriptor[:18]:18} {r.side:6} "
            f"{_fmt_odds(r.american_odds):>6} "
            f"{_fmt_pct(r.model_prob):>6} {_fmt_pct(r.implied_prob):>7} "
            f"{_fmt_pct(r.edge):>6} {_fmt_pct(r.kelly_full):>6} "
            f"{r.risk_bucket:6} ${r.stake:7.2f}"
        )
        for note in r.rationale:
            print(f"    why: {note}")
        print()

    svc.store.close()
    return 0


def cmd_log_bet(args, paths: AppPaths) -> int:
    svc = _service(paths)
    bet = svc.log_bet(
        game_id=args.game,
        market=args.market,
        side=args.side,
        american_odds=args.odds,
        stake=args.stake,
        player=args.player,
        threshold=args.threshold,
        line=args.line,
    )
    svc.store.close()
    print(
        f"Logged bet #{bet.id}: ${bet.stake:.2f} on {bet.side} {bet.market} "
        f"@ {_fmt_odds(bet.american_odds)}"
    )
    return 0


def cmd_settle(args, paths: AppPaths) -> int:
    svc = _service(paths)
    bet = svc.settle_bet(args.id, args.result)
    bankroll = svc.store.get_bankroll()
    svc.store.close()
    print(
        f"Settled #{bet.id} as {bet.result}. "
        f"Payout ${bet.payout:+.2f}. New bankroll: ${bankroll:.2f}"
    )
    return 0


def cmd_week(args, paths: AppPaths) -> int:
    svc = _service(paths)
    s = svc.week_summary()
    goal = s["weekly_goal"]
    profit = s["week_profit"]
    pct = (profit / goal * 100.0) if goal else 0.0
    print(f"Week of {s['week_anchor']}")
    print(f"  Bankroll:     ${s['bankroll']:.2f} (started week at ${s['starting_bankroll']:.2f})")
    print(f"  Weekly goal:  ${goal:.2f}")
    print(f"  Week profit:  ${profit:+.2f} ({pct:+.1f}% of goal)")
    print(f"  Days left:    {s['days_remaining']}")
    print(f"  Risk on open: ${s['open_risk']:.2f}")
    if s["open_bets"]:
        print("  Open bets:")
        for b in s["open_bets"]:
            print(f"    #{b.id} {b.game_id} {b.side} {b.market} "
                  f"@ {_fmt_odds(b.american_odds)} for ${b.stake:.2f}")
    svc.store.close()
    return 0


def cmd_status(args, paths: AppPaths) -> int:
    svc = _service(paths)
    s = svc.week_summary()
    n_bets = len(svc.store.list_bets())
    print(
        f"Bankroll=${s['bankroll']:.2f} "
        f"Goal=${s['weekly_goal']:.2f} "
        f"Risk={s['risk_tolerance']} "
        f"Bets logged={n_bets}"
    )
    svc.store.close()
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

    pa = sub.add_parser("advise", help="Top-3 recommended bets per day")
    pa.set_defaults(func=cmd_advise)

    pl = sub.add_parser("log-bet", help="Log a bet you placed")
    pl.add_argument("--game", required=True)
    pl.add_argument("--market", required=True)
    pl.add_argument("--side", required=True)
    pl.add_argument("--odds", type=int, required=True)
    pl.add_argument("--stake", type=float, required=True)
    pl.add_argument("--player", default=None)
    pl.add_argument("--threshold", type=float, default=None)
    pl.add_argument("--line", type=float, default=None)
    pl.set_defaults(func=cmd_log_bet)

    ps = sub.add_parser("settle", help="Settle a logged bet")
    ps.add_argument("--id", type=int, required=True)
    ps.add_argument("--result", choices=["win", "loss", "push"], required=True)
    ps.set_defaults(func=cmd_settle)

    pw = sub.add_parser("week", help="Weekly pace, goal progress, open bets")
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
