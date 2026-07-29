"""End-to-end API tests against the seeded temp DB."""

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


def test_sets(client):
    s = client.get("/sets", params={"game": "pokemon"}).json()
    assert any(x["abbreviation"] == "PRE" for x in s)


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
