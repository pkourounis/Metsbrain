"""FastAPI web UI. Same Service the CLI uses — just a different skin.

Start with `python -m metsbrain serve` and hit http://127.0.0.1:8765 on
your phone's browser (or laptop). No auth, single-user, local-only.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AppPaths
from .service import Service
from .store import Store


BASE = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE / "templates"))


def _drawdown_active(summary: dict) -> bool:
    start = summary["starting_bankroll"]
    if start <= 0:
        return False
    return (start - summary["bankroll"]) / start > 0.25


def create_app(paths: AppPaths | None = None, service_factory=None) -> FastAPI:
    """Build the FastAPI app.

    `service_factory` lets tests inject a pre-built Service (with its own
    temp DB + seed data). In production it defaults to opening the configured
    SQLite file per-request.
    """
    paths = paths or AppPaths()
    app = FastAPI(title="Metsbrain")
    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    def get_service() -> Service:
        if service_factory is not None:
            return service_factory()
        return Service(Store(paths.db_file))

    # --- Today --------------------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def today(request: Request):
        svc = get_service()
        try:
            summary = svc.week_summary()
            banner = None
            recs = []
            if summary["bankroll"] <= 0:
                banner = "Run `python -m metsbrain init` to set your bankroll and goal."
            elif summary["weekly_goal"] > 0 and summary["week_profit"] >= summary["weekly_goal"]:
                banner = "Weekly goal hit — locked to low-risk picks only until Monday."
                recs = svc.advise(persist=True)
            elif _drawdown_active(summary):
                banner = "Weekly drawdown > 25%. Cool-down in effect until Monday."
            else:
                recs = svc.advise(persist=True)
            return TEMPLATES.TemplateResponse(
                request,
                "today.html",
                {"recs": recs, "summary": summary, "banner": banner},
            )
        finally:
            svc.store.close()

    @app.post("/log-bet")
    def log_bet(
        game_id: str = Form(...),
        market: str = Form(...),
        side: str = Form(...),
        american_odds: int = Form(...),
        stake: float = Form(...),
        player: str | None = Form(None),
        threshold: float | None = Form(None),
        line: float | None = Form(None),
    ):
        svc = get_service()
        try:
            svc.log_bet(
                game_id=game_id, market=market, side=side,
                american_odds=american_odds, stake=stake,
                player=(player or None), threshold=threshold, line=line,
            )
        finally:
            svc.store.close()
        return RedirectResponse("/week", status_code=303)

    # --- Week ---------------------------------------------------------------

    @app.get("/week", response_class=HTMLResponse)
    def week(request: Request):
        svc = get_service()
        try:
            summary = svc.week_summary()
            recent = svc.store.list_bets()
            recent_settled = [b for b in recent if b.result != "open"][-10:][::-1]
            return TEMPLATES.TemplateResponse(
                request,
                "week.html",
                {"summary": summary, "recent_settled": recent_settled},
            )
        finally:
            svc.store.close()

    @app.post("/settle/{bet_id}")
    def settle(bet_id: int, result: str = Form(...)):
        svc = get_service()
        try:
            svc.settle_bet(bet_id, result)
        finally:
            svc.store.close()
        return RedirectResponse("/week", status_code=303)

    # --- Enter odds ---------------------------------------------------------

    @app.get("/enter-odds", response_class=HTMLResponse)
    def enter_odds_index(request: Request):
        svc = get_service()
        try:
            games = svc.upcoming_games()
            return TEMPLATES.TemplateResponse(
                request, "enter_odds_index.html", {"games": games},
            )
        finally:
            svc.store.close()

    @app.get("/enter-odds/{game_id}", response_class=HTMLResponse)
    def enter_odds_form(request: Request, game_id: str, saved: int = 0):
        svc = get_service()
        try:
            games = svc.upcoming_games()
            game = next((g for g in games if g.game_id == game_id), None)
            if game is None:
                return HTMLResponse(f"Unknown game {game_id}", status_code=404)
            return TEMPLATES.TemplateResponse(
                request,
                "enter_odds_form.html",
                {"game": game, "saved": bool(saved)},
            )
        finally:
            svc.store.close()

    @app.post("/enter-odds/{game_id}")
    def enter_odds_submit(
        game_id: str,
        market: str = Form(...),
        side: str = Form(...),
        american_odds: int = Form(...),
        player: str | None = Form(None),
        threshold: float | None = Form(None),
        line: float | None = Form(None),
    ):
        svc = get_service()
        try:
            svc.enter_odds(
                game_id=game_id, market=market, side=side,
                american_odds=american_odds,
                player=(player or None), threshold=threshold, line=line,
            )
        finally:
            svc.store.close()
        return RedirectResponse(f"/enter-odds/{game_id}?saved=1", status_code=303)

    return app
