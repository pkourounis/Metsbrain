"""SQLite persistence layer. Stdlib only, no ORM."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

from .models import LoggedBet, Recommendation


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weeks (
    anchor            TEXT PRIMARY KEY,
    starting_bankroll REAL NOT NULL,
    weekly_goal       REAL NOT NULL,
    risk_tolerance    TEXT NOT NULL,
    ending_bankroll   REAL
);

CREATE TABLE IF NOT EXISTS games (
    game_id  TEXT PRIMARY KEY,
    date     TEXT NOT NULL,
    opponent TEXT NOT NULL,
    home     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     TEXT NOT NULL,
    snapshot_at TEXT NOT NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS offered_lines (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL,
    market        TEXT NOT NULL,
    side          TEXT NOT NULL,
    player        TEXT,
    threshold     REAL,
    american_odds INTEGER NOT NULL,
    line          REAL,
    entered_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL,
    game_date     TEXT NOT NULL,
    market        TEXT NOT NULL,
    side          TEXT NOT NULL,
    player        TEXT,
    threshold     REAL,
    american_odds INTEGER NOT NULL,
    line          REAL,
    model_prob    REAL NOT NULL,
    implied_prob  REAL NOT NULL,
    edge          REAL NOT NULL,
    kelly_full    REAL NOT NULL,
    stake         REAL NOT NULL,
    risk_bucket   TEXT NOT NULL,
    rationale     TEXT NOT NULL,
    advised_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER,
    game_id           TEXT NOT NULL,
    market            TEXT NOT NULL,
    side              TEXT NOT NULL,
    player            TEXT,
    threshold         REAL,
    line              REAL,
    american_odds     INTEGER NOT NULL,
    stake             REAL NOT NULL,
    placed_at         TEXT NOT NULL,
    result            TEXT NOT NULL DEFAULT 'open',
    payout            REAL NOT NULL DEFAULT 0.0,
    settled_at        TEXT
);
"""


def this_monday(today: date | None = None) -> str:
    today = today or date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


class Store:
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # --- app_meta ------------------------------------------------------------

    def get_meta(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM app_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO app_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_bankroll(self) -> float:
        v = self.get_meta("bankroll")
        return float(v) if v is not None else 0.0

    def set_bankroll(self, amount: float) -> None:
        self.set_meta("bankroll", f"{amount:.2f}")

    def get_weekly_goal(self) -> float:
        v = self.get_meta("weekly_goal")
        return float(v) if v is not None else 0.0

    def get_risk_tolerance(self) -> str:
        return self.get_meta("risk_tolerance") or "medium"

    # --- weeks ---------------------------------------------------------------

    def ensure_week(self, *, bankroll: float, weekly_goal: float, risk: str) -> str:
        """Guarantee a `weeks` row exists for this Monday. Closes any prior open week."""
        anchor = this_monday()

        # Close any earlier open weeks with current bankroll.
        with self.tx() as c:
            c.execute(
                "UPDATE weeks SET ending_bankroll = ? "
                "WHERE ending_bankroll IS NULL AND anchor < ?",
                (bankroll, anchor),
            )

        row = self._conn.execute(
            "SELECT anchor FROM weeks WHERE anchor = ?", (anchor,)
        ).fetchone()
        if not row:
            with self.tx() as c:
                c.execute(
                    "INSERT INTO weeks(anchor, starting_bankroll, weekly_goal, risk_tolerance) "
                    "VALUES (?, ?, ?, ?)",
                    (anchor, bankroll, weekly_goal, risk),
                )
        return anchor

    def current_week_starting_bankroll(self) -> float:
        anchor = this_monday()
        row = self._conn.execute(
            "SELECT starting_bankroll FROM weeks WHERE anchor = ?", (anchor,)
        ).fetchone()
        return float(row["starting_bankroll"]) if row else 0.0

    # --- feature snapshots ---------------------------------------------------

    def save_snapshot(self, game_id: str, payload: dict) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO feature_snapshots(game_id, snapshot_at, payload) VALUES (?, ?, ?)",
                (game_id, datetime.now().isoformat(timespec="seconds"),
                 json.dumps(payload, sort_keys=True)),
            )
            return cur.lastrowid

    # --- recommendations -----------------------------------------------------

    def save_recommendation(self, r: Recommendation) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO recommendations("
                " game_id, game_date, market, side, player, threshold,"
                " american_odds, line, model_prob, implied_prob, edge,"
                " kelly_full, stake, risk_bucket, rationale, advised_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    r.game_id, r.game_date, r.market, r.side, r.player, r.threshold,
                    r.american_odds, r.line, r.model_prob, r.implied_prob, r.edge,
                    r.kelly_full, r.stake, r.risk_bucket, json.dumps(r.rationale),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return cur.lastrowid

    # --- bets ----------------------------------------------------------------

    def insert_bet(self, bet: LoggedBet) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO bets("
                " recommendation_id, game_id, market, side, player, threshold, line,"
                " american_odds, stake, placed_at, result, payout, settled_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    bet.recommendation_id, bet.game_id, bet.market, bet.side,
                    bet.player, bet.threshold, bet.line, bet.american_odds,
                    bet.stake, bet.placed_on, bet.result, bet.payout, bet.settled_at,
                ),
            )
            return cur.lastrowid

    def update_bet_settlement(self, bet_id: int, result: str, payout: float) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE bets SET result = ?, payout = ?, settled_at = ? WHERE id = ?",
                (result, payout, datetime.now().isoformat(timespec="seconds"), bet_id),
            )

    def get_bet(self, bet_id: int) -> Optional[LoggedBet]:
        row = self._conn.execute(
            "SELECT * FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
        return _row_to_bet(row) if row else None

    def list_bets(self, *, since: str | None = None, only_open: bool = False) -> list[LoggedBet]:
        sql = "SELECT * FROM bets WHERE 1=1"
        params: list = []
        if since is not None:
            sql += " AND placed_at >= ?"
            params.append(since)
        if only_open:
            sql += " AND result = 'open'"
        sql += " ORDER BY id ASC"
        rows = self._conn.execute(sql, params).fetchall()
        return [_row_to_bet(r) for r in rows]

    def week_profit(self) -> float:
        anchor = this_monday()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(payout), 0.0) AS p FROM bets "
            "WHERE result != 'open' AND placed_at >= ?",
            (anchor,),
        ).fetchone()
        return float(row["p"]) if row else 0.0

    def days_remaining_in_week(self) -> int:
        anchor = date.fromisoformat(this_monday())
        end = anchor + timedelta(days=6)
        return max(0, (end - date.today()).days)


def _row_to_bet(row: sqlite3.Row) -> LoggedBet:
    return LoggedBet(
        id=row["id"],
        game_id=row["game_id"],
        market=row["market"],
        side=row["side"],
        american_odds=row["american_odds"],
        stake=row["stake"],
        placed_on=row["placed_at"],
        result=row["result"],
        payout=row["payout"],
        player=row["player"],
        threshold=row["threshold"],
        line=row["line"],
        recommendation_id=row["recommendation_id"],
        settled_at=row["settled_at"],
    )
