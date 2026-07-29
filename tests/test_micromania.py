"""Offline tests for the Micromania scraper.

No network, no browser: exercises the HTML parsers against bundled fixtures
(a real category-grid dump captured by the POC, plus two synthetic SFCC product
detail pages) and checks the modules import cleanly + the categorize step.
Run: `pytest`.
"""
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from scraper import micromania_parse as mp

FIX = Path(__file__).parent / "fixtures"
LISTING = FIX / "micromania_listing.html"
PDP_IN = FIX / "micromania_pdp_instock.html"
PDP_OUT = FIX / "micromania_pdp_outofstock.html"


# --------------------------------------------------------------------------- #
# platform_pid extraction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("url, pid", [
    ("https://www.micromania.fr/p/pack-portfolio-boosters-pokemon-me-3-equilibre-parfait-158435.html", "158435"),
    ("/p/coffret--pokemon-collection-illustration-premiers-partenaires-serie-2-160611.html", "160611"),
    ("https://www.micromania.fr/p/deck-pokemon-deck-des-championnats-du-monde-2025-158432.html?x=1", "158432"),
    ("https://www.micromania.fr/c/cartespokemon", None),
])
def test_pid_from_url(url, pid):
    assert mp.pid_from_url(url) == pid


# --------------------------------------------------------------------------- #
# Price text parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text, val", [
    ("19,99 €", 19.99),
    ("4,99 €", 4.99),
    ("1 299,00 €", 1299.00),
    ("Gratuit", None),
    ("", None),
])
def test_parse_price_text(text, val):
    assert mp.parse_price_text(text) == val


# --------------------------------------------------------------------------- #
# Listing grid parsing (real captured page)
# --------------------------------------------------------------------------- #
def test_parse_listing_tiles_real_fixture():
    rows = mp.parse_listing_tiles(LISTING.read_text(encoding="utf-8"))
    assert len(rows) >= 10
    # Every tile must have an id, a title and a URL with a matching id.
    for r in rows:
        assert r["platform_pid"] and r["platform_pid"].isdigit()
        assert r["title"]
        assert r["url"] and r["platform_pid"] in r["url"]
    # Price + availability come from data-gtm and should be near-complete.
    assert sum(1 for r in rows if r["price"] is not None) >= len(rows) - 1
    assert sum(1 for r in rows if r["available"] is not None) >= len(rows) - 1


def test_listing_specific_known_product():
    rows = {r["platform_pid"]: r for r in
            mp.parse_listing_tiles(LISTING.read_text(encoding="utf-8"))}
    p = rows["158435"]
    assert p["price"] == 19.99
    assert p["available"] == 1
    assert "Portfolio" in p["title"]
    # An out-of-stock product (dispoweb 0) is read as available=0, not dropped.
    assert rows["160611"]["available"] == 0


def test_listing_no_duplicate_pids():
    rows = mp.parse_listing_tiles(LISTING.read_text(encoding="utf-8"))
    pids = [r["platform_pid"] for r in rows]
    assert len(pids) == len(set(pids))


# --------------------------------------------------------------------------- #
# Product detail parsing (synthetic SFCC PDPs)
# --------------------------------------------------------------------------- #
def test_pdp_in_stock():
    soup = BeautifulSoup(PDP_IN.read_text(encoding="utf-8"), "html.parser")
    assert mp.parse_price(soup) == 4.99
    assert mp.parse_availability(soup) == 1
    assert "Booster" in mp.parse_detail_title(soup)
    assert "scellé" in mp.parse_detail_description(soup).lower()


def test_pdp_out_of_stock():
    soup = BeautifulSoup(PDP_OUT.read_text(encoding="utf-8"), "html.parser")
    assert mp.parse_price(soup) == 19.99
    # Disabled add-to-cart button + rupture text => out of stock.
    assert mp.parse_availability(soup) == 0


def test_pdp_availability_text_out_before_in():
    # Guard the classic "indisponible" contains "disponible" trap.
    html = ('<div class="availability"><div class="availability-msg">'
            'Produit indisponible</div></div>')
    assert mp.parse_availability(BeautifulSoup(html, "html.parser")) == 0


# --------------------------------------------------------------------------- #
# Categorization wiring (sealed gate + kind on real titles)
# --------------------------------------------------------------------------- #
def test_categorize_keeps_sealed_drops_accessories():
    from scraper.discover_micromania import categorize
    rows = mp.parse_listing_tiles(LISTING.read_text(encoding="utf-8"))
    for r in rows:
        r["description"] = ""
    kept = categorize(rows)
    titles = " ".join(k["title"].lower() for k in kept)
    # Sealed products survive...
    assert any("booster" in k["title"].lower() for k in kept)
    # ...accessories do not.
    assert "sleeve" not in titles
    assert "classeur" not in titles
    # Every kept row is tagged pokemon-FR with a kind.
    for k in kept:
        assert k["language"] == "fr"
        assert k["kind"]


# --------------------------------------------------------------------------- #
# Import smoke tests (no browser launched)
# --------------------------------------------------------------------------- #
def test_imports():
    import scraper.stealth_browser  # noqa: F401
    import scraper.discover_micromania  # noqa: F401
    import scraper.fetch_micromania  # noqa: F401
    from scraper.run import FETCHERS
    assert any(label == "Micromania" for label, _, _ in FETCHERS)


def test_fetch_micromania_noop_outside_pokemon():
    # Must return [] without launching a browser when scope excludes pokemon.
    from scraper.fetch_micromania import fetch_micromania_all
    assert fetch_micromania_all(["optcg"]) == []


def test_challenge_detection():
    from scraper.stealth_browser import looks_like_challenge
    assert looks_like_challenge("<html>incident id 123</html>", 403) is True
    assert looks_like_challenge("x" * 200, 429) is True
    assert looks_like_challenge("<html>" + "x" * 50000 + "</html>", 200) is False
    assert looks_like_challenge(None, 200) is True
