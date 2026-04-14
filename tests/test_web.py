import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from metsbrain.service import Service
from metsbrain.store import Store
from metsbrain.web import create_app


@pytest.fixture
def client():
    tmp = tempfile.TemporaryDirectory()
    db_path = os.path.join(tmp.name, "metsbrain.db")

    # Seed the DB with a live bankroll so pages aren't in the "init first" state.
    seed = Service(Store(db_path))
    seed.init_app(bankroll=1000, weekly_goal=150, risk="medium")
    seed.store.close()

    def factory():
        return Service(Store(db_path))

    app = create_app(service_factory=factory)
    with TestClient(app) as c:
        yield c
    tmp.cleanup()


def test_today_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Metsbrain" in r.text
    # Summary block should show our seeded bankroll.
    assert "$1000.00" in r.text


def test_week_renders(client):
    r = client.get("/week")
    assert r.status_code == 200
    assert "Bankroll" in r.text


def test_enter_odds_index_lists_games(client):
    r = client.get("/enter-odds")
    assert r.status_code == 200
    # SampleDataProvider returns a Mets slate; at least one game_id should appear.
    assert "NYM-vs" in r.text


def test_enter_odds_submit_persists_override(client):
    # Pick a sample game from the slate and push an odds override.
    idx = client.get("/enter-odds")
    assert idx.status_code == 200
    # Brittle on formatting, robust on presence: extract a game id.
    import re
    m = re.search(r"/enter-odds/(NYM-vs-[A-Z]{3}-\d{4}-\d{2}-\d{2})", idx.text)
    assert m, "expected at least one game link in enter_odds_index"
    game_id = m.group(1)

    r = client.post(
        f"/enter-odds/{game_id}",
        data={"market": "moneyline", "side": "NYM", "american_odds": -130},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith(f"/enter-odds/{game_id}")

    # Reload the form and confirm our -130 shows up in the "currently offered" table.
    form = client.get(f"/enter-odds/{game_id}?saved=1")
    assert form.status_code == 200
    assert "-130" in form.text


def test_log_bet_and_settle_flow(client):
    # Log a bet via the web form, then settle it.
    r = client.post(
        "/log-bet",
        data={
            "game_id": "NYM-vs-MIA-test",
            "market": "moneyline",
            "side": "NYM",
            "american_odds": -120,
            "stake": 20.0,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/week"

    week = client.get("/week")
    assert week.status_code == 200
    assert "NYM-vs-MIA-test" in week.text

    # Settle the bet as a win.
    # Find its id from the week page (first settle form posts to /settle/{id}).
    import re
    m = re.search(r"/settle/(\d+)", week.text)
    assert m, "expected an open bet to settle"
    bet_id = int(m.group(1))

    r2 = client.post(f"/settle/{bet_id}", data={"result": "win"}, follow_redirects=False)
    assert r2.status_code == 303

    week2 = client.get("/week")
    assert "win" in week2.text.lower()
