"""Pull-rate odds for OPTCG — user-sourced approximate rates (classic sets).

Rates are the average number of **packs** opened to hit *any* card of a tier
(user estimate; "paquet" = "booster" = one pack). A *specific* card of that tier
then takes `packs_per_any × distinct_in_tier` packs on average — the pull rate
that drives supply in the valuation model. Valid for classic sets (NOT PRB01/02).

    SR            1 / 3 packs        parallel/alt  1 / 8 packs
    SEC           1 / 30 packs       SP            1 / 144 packs
    Event Manga   1 / 288 packs      Manga         1 / 864 packs

Common/Uncommon and classic (non-parallel) leaders are not tracked. `R` has no
user-given rate — a conservative placeholder (high supply); tune when sourced.
Manga / Event-Manga aren't separable on Limitless, so alt-arts fold into `alt`.
"""
from __future__ import annotations

# Average packs to open for ANY card of the tier (classic sets).
PACKS_PER_ANY = {
    "R": 1.0,          # placeholder: no user rate; R is high-supply / low-value
    "SR": 3.0,
    "alt": 8.0,        # parallel / alt-art (folds Manga & Event-Manga in v1)
    "SEC": 30.0,
    "SP": 144.0,
    "TR": 288.0,       # placeholder: treat Treasure Rare like Event-Manga tier
    "manga": 864.0,
    "event_manga": 288.0,
    "godpack": 2000.0,  # placeholder: god-pack red-letter print, ultra-rare (unknown rate)
}

# Base rarities that are *not* tracked as standalone cards.
_SKIP_BASE = {"C", "UC", "L", "P", "?"}


# Limitless print-version kind → pull-rate tier. "other" (cross-product promo /
# collection reprints) has no booster pull rate → untracked.
_KIND_TIER = {"aa": "alt", "manga": "manga", "fa": "SP", "special": "SP", "godpack": "godpack"}


_EVENT_TYPES = {"Event", "Stage"}


def version_tier(rarity: str, kind: str, card_type: str | None = None) -> str | None:
    """Map a printing (base rarity + version kind + card type) to a pull-rate tier.

    An alt-art on an Event/Stage card is an "event manga / event parallel"
    (~1/288), distinct from a Character's parallel (1/8) or manga (1/864).
    """
    if kind == "base":
        if rarity in _SKIP_BASE:
            return None                 # base common/uncommon/leader: not tracked
        return rarity if rarity in PACKS_PER_ANY else None
    if kind == "godpack":
        return "godpack"
    if kind not in _KIND_TIER:
        return None                     # "other" (cross-product reprint): excluded
    if card_type in _EVENT_TYPES:
        return "event_manga"            # event parallel / event manga (~1/288)
    return _KIND_TIER[kind]             # aa / manga / special → alt / manga / SP


def distinct_in_tiers(cards: list[dict], set_code: str) -> dict[str, int]:
    """Count distinct printings per tier within a set (pull-rate denominator)."""
    counts: dict[str, int] = {}
    for c in cards:
        if c.get("set_code") != set_code:
            continue
        for v in c.get("versions", []):
            tier = version_tier(c["rarity"], v["kind"], c.get("type"))
            if tier:
                counts[tier] = counts.get(tier, 0) + 1
    return counts


def pull_rate(tier: str, distinct_in_tier: int) -> float:
    """Average packs to open to obtain ONE specific card of this tier."""
    per_any = PACKS_PER_ANY.get(tier)
    if per_any is None or distinct_in_tier <= 0:
        raise ValueError(f"no odds for tier {tier!r} (distinct={distinct_in_tier})")
    return per_any * distinct_in_tier
