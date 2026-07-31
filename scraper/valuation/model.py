"""Card fair-value model — first draft (OPTCG).

Goal: flag whether a single card is **over- or under-valued** vs its Cardmarket
market price, by modelling the two forces behind a card's price:

    price(card)  ≈  DEMAND(card) / SUPPLY(card)

SUPPLY comes from the **pull rate** — how many packs you must open, on average,
to get one specific copy:

    packs_per_any_of_rarity = box_packs / hits_per_box[rarity]
    pull_rate(card)         = packs_per_any_of_rarity × distinct_in_rarity
    copies_per_box(card)    = box_packs / pull_rate           (expected copies/box)

  e.g. an SR that falls ~7×/box of 24 packs => every 24/7 ≈ 3.4 packs; with 8
  different SRs => a *specific* SR every 3.4 × 8 ≈ 27 packs.

DEMAND is a multiplier capturing why one card beats another of equal rarity:
  - playability   (0..3): a played rare can beat a dead SR.
  - character_pop (0..3): Luffy/Zoro/Ace sell regardless of play.
  - alt_art       (bool): parallel / manga rares carry a premium.
  - reprint_risk  (0..1): a likely reprint discounts the card.

FAIR VALUE (relative, value-conserving). A booster box yields a pool of single
value ≈ box_price × recovery. We split that pool across all copies a box produces
so that price ∝ demand / supply, i.e.

    fair_value(card) ∝ demand_weight(card) × pull_rate(card)

normalised so that Σ_cards fair_value × copies_per_box = pool. So a rarer card
(higher pull_rate) and/or a more-demanded card gets a higher per-copy price, and
the whole set's modelled single value ties back to the real (Cardmarket) box price.

VERDICT: ratio = market_price / fair_value.
  ratio ≫ 1 → overvalued (speculative), ratio ≪ 1 → undervalued (opportunity).

This draft uses hand-set weights (an expert prior) and a per-set normalisation.
The real calibration comes next: fit `recovery` + the demand weights by regressing
the whole One Piece singles universe (Cardmarket prices we already ingest) on these
features — the residuals then *are* the over/under signal. Odds tables + playability
are the inputs still to source (see the handover questions).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Weights:
    recovery: float = 0.75      # fraction of box price recoverable as chase singles
    w_play: float = 0.9         # playability contribution per tier
    w_pop: float = 0.35         # character-popularity contribution per tier
    alt_mult: float = 1.9       # alt-art / manga premium
    w_reprint: float = 0.6      # max discount from reprint risk
    over_th: float = 1.30       # market/fair above this = overvalued
    under_th: float = 0.77      # below this = undervalued


DEFAULT_WEIGHTS = Weights()


@dataclass
class SetOdds:
    box_packs: int                       # packs per booster box (OPTCG: usually 24)
    hits_per_box: dict[str, float]       # avg copies of each rarity per box
    distinct_in_rarity: dict[str, int]   # number of different cards of each rarity


@dataclass
class Card:
    code: str
    name: str
    rarity: str
    market_price: float | None = None    # Cardmarket trend (EUR)
    playability: float = 0.0             # 0..3
    character_pop: float = 0.0           # 0..3
    is_alt: bool = False
    reprint_risk: float = 0.0            # 0..1


@dataclass
class Valuation:
    card: Card
    pull_rate: float
    fair_value: float
    ratio: float | None
    verdict: str                         # surévaluée | sous-évaluée | juste | prix inconnu
    signal: float | None                 # signed % gap (market vs fair)


def pull_rate(card: Card, odds: SetOdds) -> float:
    """Average packs to open to get ONE specific copy of this card."""
    hits = odds.hits_per_box.get(card.rarity)
    distinct = odds.distinct_in_rarity.get(card.rarity)
    if not hits or not distinct:
        raise ValueError(f"Missing odds for rarity {card.rarity!r}")
    return (odds.box_packs / hits) * distinct


def demand_weight(card: Card, w: Weights = DEFAULT_WEIGHTS) -> float:
    d = 1.0 + w.w_play * card.playability + w.w_pop * card.character_pop
    if card.is_alt:
        d *= w.alt_mult
    return d * (1.0 - w.w_reprint * card.reprint_risk)


def evaluate_set(cards: list[Card], odds: SetOdds, box_price: float,
                 w: Weights = DEFAULT_WEIGHTS) -> list[Valuation]:
    """Fair value + verdict for every card, normalised so the set's total modelled
    single value equals the box value pool. Pass the full set for best results."""
    pool = box_price * w.recovery
    wsum = sum(demand_weight(c, w) for c in cards) or 1.0
    unit = pool / (odds.box_packs * wsum)   # € per (weight × pull_rate)

    out: list[Valuation] = []
    for c in cards:
        pr = pull_rate(c, odds)
        fv = unit * demand_weight(c, w) * pr
        if c.market_price is None or fv <= 0:
            out.append(Valuation(c, pr, fv, None, "prix inconnu", None))
            continue
        ratio = c.market_price / fv
        verdict = ("surévaluée" if ratio >= w.over_th
                   else "sous-évaluée" if ratio <= w.under_th else "juste")
        out.append(Valuation(c, pr, fv, ratio, verdict, round((ratio - 1) * 100, 1)))
    return out


def _demo():
    # PLACEHOLDER odds — the user's SR example (7 hits/box, 8 distinct) + siblings.
    odds = SetOdds(
        box_packs=24,
        hits_per_box={"L": 1.0, "SR": 7.0, "SEC": 0.5, "R": 24.0},
        distinct_in_rarity={"L": 4, "SR": 8, "SEC": 2, "R": 30},
    )
    box_price = 180.0  # EUR — a real box trend from our Cardmarket data plugs in here.

    cards = [
        Card("SR-A", "SR jouée (staple)",   "SR",  market_price=18.0, playability=3, character_pop=2),
        Card("SR-B", "SR non jouée",         "SR",  market_price=18.0, playability=0, character_pop=1),
        Card("R-C",  "Rare très jouée",      "R",   market_price=6.0,  playability=3, character_pop=1),
        Card("SEC-D","Secret alt Luffy",     "SEC", market_price=120.0, playability=1, character_pop=3, is_alt=True),
        Card("SR-E", "SR alt hype (spec)",   "SR",  market_price=90.0, playability=1, character_pop=3, is_alt=True),
    ]

    print(f"Demo (PLACEHOLDER odds) — box {box_price:.0f}€, pool {box_price*DEFAULT_WEIGHTS.recovery:.0f}€\n")
    print(f"{'card':6} {'rar':4} {'pull':>6} {'fair€':>7} {'marché€':>8} {'ratio':>6}  verdict")
    for v in evaluate_set(cards, odds, box_price):
        c = v.card
        print(f"{c.code:6} {c.rarity:4} {v.pull_rate:6.1f} {v.fair_value:7.2f} "
              f"{(c.market_price or 0):8.2f} {(v.ratio or 0):6.2f}  {v.verdict} "
              f"({'+' if (v.signal or 0) >= 0 else ''}{v.signal}%)")


if __name__ == "__main__":
    _demo()
