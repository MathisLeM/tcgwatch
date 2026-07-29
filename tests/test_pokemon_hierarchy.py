"""Offline tests for the Pokemon block > set > article-type navigation builder.

Exercises `scraper.games.pokemon_hierarchy.build_hierarchy` against the bundled
TCGdex reference with a small synthetic count map — no network, no DB.
"""
from scraper.games import pokemon
from scraper.games.pokemon_hierarchy import build_hierarchy


def _sample_counts():
    # (language, set_code, kind) -> tracked-listing count
    return {
        ("fr", "sv08.5", "display"): 8,
        ("fr", "sv08.5", "etb"): 3,
        ("fr", "me01", "booster"): 12,
        ("ja", "SV9", "display"): 5,       # JP set, same 'sv' block
        ("fr", "", "coffret"): 4,          # setless standalone tin
    }


def test_hierarchy_has_three_levels_block_set_kind():
    h = build_hierarchy(_sample_counts())
    assert h["blocks"], "expected at least one block"
    block = h["blocks"][0]
    assert {"block", "name", "sets"} <= block.keys()
    a_set = block["sets"][0]
    assert {"set_code", "language", "kinds", "product_count"} <= a_set.keys()


def test_blocks_ordered_newest_era_first():
    h = build_hierarchy(_sample_counts())
    ids = [b["block"] for b in h["blocks"]]
    # Mega Evolution ('me') must come before Scarlet & Violet ('sv'), which comes
    # before Sword & Shield ('swsh') — the curated display order.
    assert ids.index("me") < ids.index("sv") < ids.index("swsh")


def test_counts_roll_up_from_kind_to_set_to_block():
    h = build_hierarchy(_sample_counts())
    blocks = {b["block"]: b for b in h["blocks"]}
    # sv block aggregates FR sv08.5 (8+3) plus JP SV9 (5) = 16.
    assert blocks["sv"]["product_count"] == 16
    me = blocks["me"]
    assert me["product_count"] == 12


def test_jp_set_merged_into_international_block():
    h = build_hierarchy(_sample_counts())
    sv = next(b for b in h["blocks"] if b["block"] == "sv")
    codes = {s["set_code"] for s in sv["sets"]}
    assert "SV9" in codes and "sv08.5" in codes


def test_setless_listings_surface_in_unassigned():
    h = build_hierarchy(_sample_counts())
    assert h["unassigned"]["product_count"] == 4
    assert h["unassigned"]["kinds"][0]["kind"] == "coffret"


def test_language_filter_restricts_sets():
    h = build_hierarchy(_sample_counts(), languages=["fr"])
    langs = {s["language"] for b in h["blocks"] for s in b["sets"]}
    assert langs <= {"fr"}


def test_every_active_block_has_an_image():
    # Blocks with tracked listings should carry a resolvable image (curated or
    # a representative set logo fallback).
    h = build_hierarchy(_sample_counts())
    for b in h["blocks"]:
        if b["product_count"] > 0:
            assert b["image"], f"block {b['block']} has listings but no image"
