"""Valuation pipeline — rarity consolidation (offline) + model sanity."""

from scraper.valuation import Card, SetOdds, evaluate_set
from scraper.valuation.cards_limitless import _version_kind, parse_card_detail
from scraper.valuation.odds import distinct_in_tiers, pull_rate, version_tier
from scraper.valuation.playability import (
    aggregate,
    parse_archetype_cards,
    parse_metagame,
)
from scraper.valuation.popularity import popularity_rank, popularity_score
from scraper.valuation.rarity import canon_rarity, consolidate


def test_canon_rarity_maps_source_strings():
    assert canon_rarity("SP CARD") == "SP"
    assert canon_rarity(" sr ") == "SR"
    assert canon_rarity(None) == "?"
    assert canon_rarity("XYZ") == "XYZ"       # unknown passes through, upper-cased


def test_consolidate_aggregates_variants_and_flags_alt():
    raw = {
        "op09": [
            {"id": "OP09-051", "code": "OP09-051", "rarity": "R", "name": "Buggy",
             "type": "CHARACTER", "color": "Purple", "set": {"name": "OP-09"}},
            {"id": "OP09-051_p1", "code": "OP09-051", "rarity": "R", "name": "Buggy",
             "set": {"name": "OP-09"}},
            {"id": "OP09-051_p2", "code": "OP09-051", "rarity": "SP CARD", "name": "Buggy",
             "set": {"name": "OP-09"}},
            {"id": "OP09-119", "code": "OP09-119", "rarity": "SEC", "name": "Luffy",
             "type": "CHARACTER"},
            {"id": "", "code": "", "rarity": "C"},      # junk row ignored
        ],
    }
    cat = consolidate(raw)

    buggy = cat["OP09-051"]
    assert buggy["rarity"] == "R"                 # base printing rarity, not the SP parallel
    assert buggy["rarities"] == ["R", "SP"]       # every printing's rarity
    assert buggy["has_parallel"] is True and buggy["n_parallels"] == 2
    assert buggy["n_variants"] == 3
    assert buggy["set_code"] == "OP09" and buggy["from_booster"] is True

    luffy = cat["OP09-119"]
    assert luffy["rarity"] == "SEC" and luffy["has_parallel"] is False
    assert "" not in cat                          # empty code dropped


_META_HTML = """
<tr>
  <td>1</td>
  <td><div class="leader-icon" style="background-image: url(https://cdn/one-piece/OP11/OP11-041_EN.webp)"></div></td>
  <td><a class="deck-link" href="/decks/74"><span>Blue/Yellow</span><span>Nami</span></a></td>
  <td>1248</td>
  <td>25.00%</td>
</tr>
<tr>
  <td>2</td>
  <td><div class="leader-icon" style="background-image: url(https://cdn/one-piece/OP09/OP09-051_EN.webp)"></div></td>
  <td><a class="deck-link" href="/decks/98"><span>Blue</span><span>Buggy</span></a></td>
  <td>900</td>
  <td>5.00%</td>
</tr>
"""

_CARDS_HTML = """
<div class="decklist-card" data-count="3.70" data-id="OP14-102" data-variant="0"></div>
<div class="decklist-card" data-count="20.00" data-id="OP16-042" data-variant="0"></div>
"""


def test_parse_metagame_extracts_share_and_leader():
    meta = parse_metagame(_META_HTML)
    assert [m["id"] for m in meta] == ["74", "98"]
    assert meta[0]["name"] == "Blue/Yellow Nami"
    assert meta[0]["share"] == 0.25 and meta[0]["leader"] == "OP11-041"


def test_parse_cards_caps_illegal_copy_counts_at_four():
    cards = parse_archetype_cards(_CARDS_HTML)
    assert cards["OP14-102"] == 3.70
    assert cards["OP16-042"] == 4.0        # 20.00 clamped to the deck-legal max


def test_aggregate_weights_by_share_and_injects_leader():
    meta = parse_metagame(_META_HTML)
    cards_by_id = {"74": {"OP14-102": 4.0}, "98": {}}   # deck 98 has no card grid
    cat = aggregate(meta, cards_by_id)
    # OP14-102: only in deck 74 (share .25) at 4 copies -> exp 1.0
    assert cat["OP14-102"]["exp_copies"] == 1.0
    # leader OP09-051 injected for deck 98 (share .05, 1 copy) -> exp 0.05
    assert cat["OP09-051"]["exp_copies"] == 0.05
    # play_score is 0..3 relative to the most-played card (OP14-102 here)
    assert cat["OP14-102"]["play_score"] == 3.0


_DETAIL_HTML = """
<div class="prints-current-details">
  <span class="text-lg">Uta (EB03)</span>
  <span> Secret Rare </span>
</div>
<div class="card-prints-versions">
<table>
  <tr><th>Print</th><th>USD</th><th>EUR</th></tr>
  <tr><td><a href="https://partner.tcgplayer.com/x">Heroines Edition</a></td><td>$10</td><td>9.41 €</td></tr>
  <tr><td><a href="/cards/EB03-061?v=1">Heroines Edition aa</a></td><td>$20</td><td>17.88 €</td></tr>
  <tr><td><a href="/cards/EB03-061?v=2">Heroines Edition manga</a></td><td>$999</td><td>957.87 €</td></tr>
</table>
</div>
"""


def test_version_kind_classifies_prints():
    base = "Heroines Edition"
    assert _version_kind(base, "https://partner.tcgplayer.com/x", base) == "base"
    assert _version_kind("Heroines Edition aa", "/cards/EB03-061?v=1", base) == "aa"
    assert _version_kind("Heroines Edition manga", "/cards/EB03-061?v=2", base) == "manga"
    assert _version_kind("Heroines Edition fa", "/cards/EB03-061?v=3", base) == "fa"
    assert _version_kind(base, "/cards/EB03-024?v=2", base) == "special"     # same-name extra ≈ SP
    # a different product (promo/collection reprint) is excluded from the model
    assert _version_kind("Premium Card Collection", "/cards/EB03-024?v=4", base) == "other"


def test_parse_card_detail_reads_rarity_and_priced_versions():
    d = parse_card_detail(_DETAIL_HTML)
    assert d["rarity"] == "SEC"
    kinds = {v["kind"]: v["eur"] for v in d["versions"]}
    assert kinds == {"base": 9.41, "aa": 17.88, "manga": 957.87}


def test_version_tier_and_distinct_and_pull_rate():
    # base rarities: SR/SEC tracked, Common/Leader skipped; version kinds mapped.
    assert version_tier("SR", "base") == "SR"
    assert version_tier("C", "base") is None
    assert version_tier("L", "base") is None           # classic leader not tracked
    assert version_tier("SR", "aa") == "alt"
    assert version_tier("SEC", "manga") == "manga"
    assert version_tier("SR", "special") == "SP"
    # card type routes Event/Stage alt-arts to the event-manga tier (~1/288)
    assert version_tier("R", "aa", "Event") == "event_manga"
    assert version_tier("SR", "aa", "Character") == "alt"       # character parallel stays 1/8
    assert version_tier("R", "other", "Event") is None          # cross-product reprint excluded

    cards = [
        {"set_code": "OP15", "rarity": "SR",
         "versions": [{"kind": "base"}, {"kind": "aa"}]},
        {"set_code": "OP15", "rarity": "SEC",
         "versions": [{"kind": "base"}, {"kind": "manga"}]},
        {"set_code": "OP99", "rarity": "SR", "versions": [{"kind": "base"}]},  # other set
    ]
    d = distinct_in_tiers(cards, "OP15")
    assert d == {"SR": 1, "alt": 1, "SEC": 1, "manga": 1}
    # a specific SR among 10 distinct at 1/3 packs -> 30 packs
    assert pull_rate("SR", 10) == 30.0


def test_popularity_matches_across_name_punctuation():
    # Limitless punctuation vs poll spelling must still resolve to the right rank.
    assert popularity_rank("Monkey.D.Luffy") == 1
    assert popularity_rank("Roronoa Zoro") == 2
    assert popularity_rank("Sanji") == 4                 # poll: "Vinsmoke Sanji"
    assert popularity_rank("Trafalgar Law") == 5         # poll: "Trafalgar D. Water Law"
    assert popularity_rank("Boa Hancock") == 7
    # non-top-100 characters / event cards resolve to nothing (score 0)
    assert popularity_rank("Mamaragan") is None
    assert popularity_score("Mamaragan") == 0.0
    # score is monotone with rank: Luffy (1) > Hancock (7) > 0
    assert popularity_score("Monkey.D.Luffy") > popularity_score("Boa Hancock") > 0.0


def test_model_produces_over_and_under_spread():
    odds = SetOdds(box_packs=24, hits_per_box={"SR": 7.0, "R": 24.0},
                   distinct_in_rarity={"SR": 8, "R": 30})
    cards = [
        Card("SR-play", "played", "SR", market_price=18.0, playability=3),
        Card("SR-dead", "dead", "SR", market_price=18.0, playability=0),
    ]
    vals = {v.card.code: v for v in evaluate_set(cards, odds, box_price=180.0)}
    # same rarity + price, but the played one is under-valued vs the dead one
    assert vals["SR-play"].fair_value > vals["SR-dead"].fair_value
    assert vals["SR-play"].ratio < vals["SR-dead"].ratio
