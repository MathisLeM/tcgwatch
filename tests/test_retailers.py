"""Big-chain ("Grandes enseignes") endpoints + store-inventory parsing."""
import pytest

from api import retailers as reg
from api.services.store_inventory import apply_ats, parse_ats, parse_stores


@pytest.fixture
def live_micromania(monkeypatch):
    """Temporarily promote Micromania to `live` to exercise the drill-down path.

    No retailer ships as `live` today (the chantier "grandes enseignes" is on
    hold), but the endpoints behind the gate must keep working.
    """
    r = reg.get_by_id("micromania")
    monkeypatch.setattr(r, "status", "live")
    monkeypatch.setattr(r, "has_store_stock", True)
    return r


# ── Registry / listing ────────────────────────────────────────────────────────
def test_list_retailers(client):
    rs = client.get("/retailers").json()
    by_id = {r["id"]: r for r in rs}
    # Micromania est volontairement repassée en "soon" (POC pas assez fiable),
    # mais garde son `platform` donc son compteur de fiches déjà collectées.
    assert by_id["micromania"]["status"] == "soon"
    assert by_id["micromania"]["has_store_stock"] is False
    assert by_id["micromania"]["item_count"] >= 1          # seeded micromania product
    assert by_id["fnac"]["status"] == "blocked"            # shown but disabled


def test_no_retailer_is_live(client):
    """Garde-fou : rien ne doit repasser en `live` par inadvertance."""
    rs = client.get("/retailers").json()
    assert [r["id"] for r in rs if r["status"] == "live"] == []


def test_retailer_products_gated_when_not_live(client):
    assert client.get("/retailers/micromania/products").status_code == 409


def test_retailer_products(client, live_micromania):
    page = client.get("/retailers/micromania/products").json()
    assert page["total"] >= 1
    assert all(p["shop"] == "micromania.fr" for p in page["items"])
    # filter by game
    assert client.get("/retailers/micromania/products", params={"game": "pokemon"}).json()["total"] >= 1


def test_retailer_unknown_and_blocked(client):
    assert client.get("/retailers/nope/products").status_code == 404
    assert client.get("/retailers/fnac/products").status_code == 409      # blocked, not live


def test_store_stock_blocked_retailer(client, live_micromania):
    # fnac is blocked -> 409 before any browser work
    pid = client.get("/retailers/micromania/products").json()["items"][0]["product_id"]
    assert client.get(f"/retailers/fnac/products/{pid}/stores", params={"near": "75001"}).status_code == 409


# ── Pure store-inventory parsing (offline, no browser) ────────────────────────
_INV = {
    "stores": [
        {"ID": "HA", "name": "LES HALLES", "address1": "210 Porte Lescot", "city": "PARIS",
         "postalCode": "75001", "latitude": 48.862, "longitude": 2.347,
         "click_and_collect": True, "pickupInStore": True, "formattedPhone": "01 23"},
        {"ID": "BCY", "name": "BERCY", "address1": "Cour St-Émilion", "city": "PARIS",
         "postalCode": "75012", "latitude": 48.83, "longitude": 2.38,
         "click_and_collect": False, "pickupInStore": True},
    ]
}


def test_parse_stores():
    stores = parse_stores(_INV, limit=10)
    assert len(stores) == 2
    assert stores[0]["store_id"] == "HA"
    assert stores[0]["name"] == "LES HALLES"
    assert stores[0]["address"] == "210 Porte Lescot"
    assert stores[0]["click_and_collect"] is True
    assert stores[0]["ats_value"] is None       # not filled yet


def test_parse_ats():
    assert parse_ats({"atsValue": 0, "product": {"available": False}}) == (0, False)
    assert parse_ats({"atsValue": 3, "product": {"available": True}}) == (3, True)
    # availability inferred from qty when 'available' absent
    assert parse_ats({"atsValue": 5}) == (5, True)
    assert parse_ats({"atsValue": None}) == (None, False)


def test_apply_ats():
    stores = parse_stores(_INV)
    apply_ats(stores, {"HA": (2, True), "BCY": (0, False)})
    by_id = {s["store_id"]: s for s in stores}
    assert by_id["HA"]["ats_value"] == 2 and by_id["HA"]["available"] is True
    assert by_id["BCY"]["ats_value"] == 0 and by_id["BCY"]["available"] is False
