"""End-to-end API tests against the seeded temp DB."""

import json

import pytest

from api.config import settings


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth ────────────────────────────────────────────────────────────────────
def test_signup_login_me_logout(client):
    r = client.post("/auth/signup", json={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "a@b.com"

    # /me works with the cookie set by signup
    assert client.get("/auth/me").json()["email"] == "a@b.com"

    # duplicate email rejected
    assert client.post("/auth/signup", json={"email": "a@b.com", "password": "password123"}).status_code == 400
    # short password rejected
    assert client.post("/auth/signup", json={"email": "c@d.com", "password": "x"}).status_code == 400

    # login via form
    r = client.post("/auth/login", data={"username": "a@b.com", "password": "password123"})
    assert r.status_code == 200

    # logout clears cookie -> /me now 401
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_signup_closed_returns_403(client, monkeypatch):
    # Alpha default: public signup is closed; accounts are provisioned by admin.
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_SIGNUP", False)
    r = client.post("/auth/signup", json={"email": "closed@b.com", "password": "password123"})
    assert r.status_code == 403


def test_login_identifier_accepts_pseudo(client):
    # Identifier is free-form: a pseudo (no email format) must work end to end.
    r = client.post("/auth/signup", json={"email": "mathis_59", "password": "password123"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "mathis_59"
    # too-short identifier rejected
    assert client.post("/auth/signup", json={"email": "ab", "password": "password123"}).status_code == 400
    # login with the pseudo
    r = client.post("/auth/login", data={"username": "mathis_59", "password": "password123"})
    assert r.status_code == 200


def test_me_requires_auth(client):
    fresh = client.__class__(client.app)  # cookie-less client
    assert fresh.get("/auth/me").status_code == 401


# ── Products ────────────────────────────────────────────────────────────────
def test_list_products_and_filters(client):
    r = client.get("/products", params={"shop": "exampleshop.fr"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["status"] == "In Stock"          # latest snapshot available=1
    assert item["price_now"] == 59.9
    assert item["price_prev"] == 69.9            # previous snapshot price

    # filter by status
    assert client.get("/products", params={"status": "Out"}).json()["total"] == 0
    assert client.get("/products", params={"status": "In Stock"}).json()["total"] >= 1
    # filter by game / set / search
    assert client.get("/products", params={"game": "pokemon"}).json()["total"] >= 1
    assert client.get("/products", params={"set_code": "sv08.5"}).json()["total"] >= 1
    assert client.get("/products", params={"search": "déferlantes"}).json()["total"] >= 1
    # max price below current -> excluded
    assert client.get("/products", params={"max_price": 10}).json()["total"] == 0


def test_facets(client):
    f = client.get("/products/facets").json()
    assert "pokemon" in f["games"]
    assert "sv08.5" in f["set_codes"]


def test_price_history_one_point_per_day(client):
    pid = client.get("/products", params={"shop": "exampleshop.fr"}).json()["items"][0]["product_id"]

    # The seeded snapshots are from June 2026, so a wide window is needed to see
    # them; each is on its own day, newest last.
    h = client.get("/products/history", params={"product_id": pid, "days": 365}).json()
    assert h[str(pid)] == [
        {"d": "2026-06-01", "p": 69.9},
        {"d": "2026-06-02", "p": 59.9},
    ]

    # Requested products with nothing in the window still get a key, so the
    # dashboard never has to tell "no data" apart from "not asked for".
    narrow = client.get("/products/history", params={"product_id": pid, "days": 1}).json()
    assert narrow == {str(pid): []}


def test_price_history_batches_and_ignores_unknown_ids(client):
    items = client.get("/products").json()["items"]
    ids = [i["product_id"] for i in items[:2]]
    h = client.get(
        "/products/history",
        params=[("product_id", i) for i in ids + [999_999]] + [("days", 365)],
    ).json()
    assert set(h) == {str(i) for i in ids} | {"999999"}
    assert h["999999"] == []


def test_listing_carries_a_root_relative_image_or_none(client):
    for item in client.get("/products").json()["items"]:
        assert "image" in item
        if item["image"] is not None:
            assert not item["image"].startswith("/")
            assert item["image"].startswith("images/")


def test_sets(client):
    s = client.get("/sets", params={"game": "pokemon"}).json()
    assert any(x["abbreviation"] == "PRE" for x in s)


# ── Catalogue (multi-TCG navigation) ─────────────────────────────────────────
def test_catalog_games_lists_three_tcgs(client):
    games = {g["game"]: g for g in client.get("/catalog/games").json()}
    assert {"pokemon", "optcg"} <= set(games)
    assert games["pokemon"]["mode"] == "blocks"
    assert games["optcg"]["mode"] == "sets"
    # each game exposes a live availability count
    assert games["optcg"]["available_count"] >= 1


def test_optcg_kind_derived_without_stored_column(client):
    # OPTCG products have kind=NULL in the DB; the catalogue + product table must
    # still surface the article type, derived from the title. No DB change needed.
    d = client.get("/catalog", params={"game": "optcg"}).json()
    assert d["mode"] == "sets"
    op10 = next(s for s in d["sets"] if s["set_code"] == "OP10")
    assert op10["name"] == "Sang Royal"
    assert any(k["kind"] == "display" for k in op10["kinds"])
    # availability preview: the seeded OP10 listing is in stock at 89.9
    assert op10["available_count"] == 1
    assert op10["min_price"] == 89.9
    display = next(k for k in op10["kinds"] if k["kind"] == "display")
    assert display["available_count"] == 1 and display["min_price"] == 89.9

    # kind filter (a catalogue chip deep-link) works despite the NULL column
    r = client.get("/products", params={"game": "optcg", "set_code": "OP10", "kind": "display"})
    items = r.json()["items"]
    assert items and items[0]["kind"] == "display"
    # and the wrong kind returns nothing
    assert client.get("/products", params={"game": "optcg", "kind": "booster"}).json()["total"] == 0

    # facet dropdown is populated for OPTCG too
    assert "display" in client.get("/products/facets", params={"game": "optcg"}).json()["kinds"]


# ── Trends (Cardmarket price history) ────────────────────────────────────────
def test_trends_lists_sealed_with_delta_and_series(client):
    d = client.get("/trends", params={"category": "sealed"}).json()
    op09 = next(i for i in d if i["set_code"] == "OP09" and i["id_product"] == 768727)
    assert op09["latest"]["trend"] == 431.0
    assert op09["first_trend"] == 333.0
    assert op09["delta_pct"] == pytest.approx(29.4, abs=0.15)   # (431-333)/333*100
    assert len(op09["points"]) == 2 and op09["points"][0]["d"] == "2026-05-01"


def test_trend_detail_returns_full_history(client):
    d = client.get("/trends/768727").json()
    assert d["name"].startswith("Emperors")
    assert [p["trend"] for p in d["points"]] == [333.0, 431.0]
    assert client.get("/trends/1").status_code == 404


def test_cm_ingest_is_idempotent(tmp_path):
    # Ingest a tiny price guide targeting a tracked-but-empty product (802153).
    from scraper.cardmarket.ingest import ingest
    pg = tmp_path / "price_guide_0101.json"
    pg.write_text(json.dumps({"createdAt": "2026-01-01T00:00:00+0000", "priceGuides": [
        {"idProduct": 802153, "avg": 150.0, "low": 134.0, "trend": 140.0, "avg7": None, "avg30": None},
        {"idProduct": 999999, "avg": 1.0},   # not tracked -> ignored
    ]}), encoding="utf-8")
    assert ingest([pg])["inserted"] == 1
    assert ingest([pg])["inserted"] == 0     # re-ingest = no duplicate


# ── Favorites ───────────────────────────────────────────────────────────────
def test_favorites_crud(auth_client):
    pid = auth_client.get("/products").json()["items"][0]["product_id"]
    r = auth_client.post("/favorites", json={"product_id": pid})
    assert r.status_code == 201, r.text
    fav_id = r.json()["id"]

    assert len(auth_client.get("/favorites").json()) == 1
    # idempotent add returns the same favorite
    assert auth_client.post("/favorites", json={"product_id": pid}).json()["id"] == fav_id
    # must provide exactly one target
    assert auth_client.post("/favorites", json={}).status_code == 400

    assert auth_client.delete(f"/favorites/{fav_id}").status_code == 204
    assert len(auth_client.get("/favorites").json()) == 0


def test_favorites_require_auth(client):
    assert client.get("/favorites").status_code == 401


# ── Alerts ──────────────────────────────────────────────────────────────────
def test_alert_config_and_test_send(auth_client):
    pid = auth_client.get("/products").json()["items"][0]["product_id"]
    r = auth_client.post("/alerts", json={
        "scope_type": "product", "product_id": pid,
        "channel": "discord", "destination": "https://discord.test/webhook",
        "alert_type": "restock",
    })
    assert r.status_code == 201, r.text
    alert_id = r.json()["id"]
    assert len(auth_client.get("/alerts").json()) == 1

    # invalid channel rejected
    assert auth_client.post("/alerts", json={
        "scope_type": "product", "product_id": pid,
        "channel": "carrier-pigeon", "destination": "x",
    }).status_code == 400

    # test-send on a bogus webhook reports failure (real attempt, DNS fails)
    t = auth_client.post(f"/alerts/{alert_id}/test").json()
    assert t["success"] is False
    assert "detail" in t

    # email channel with SMTP unconfigured -> dry-run success
    r2 = auth_client.post("/alerts", json={
        "scope_type": "favorites",
        "channel": "email", "destination": "me@example.com",
        "alert_type": "any",
    })
    email_id = r2.json()["id"]
    assert auth_client.post(f"/alerts/{email_id}/test").json()["success"] is True

    assert auth_client.delete(f"/alerts/{alert_id}").status_code == 204
