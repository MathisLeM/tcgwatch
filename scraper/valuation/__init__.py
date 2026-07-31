"""Card fair-value / speculation model (OPTCG to start).

Two layers:
  - `model` — the pure over/under-valuation math (demand/supply, pull rate,
    value-conserving normalisation). No I/O, no network.
  - data adapters that feed it real features:
      * `rarity`      — card rarity / alt-art, from the keyless apitcg dump.
      * (next) playability from Limitless, price join from Cardmarket.

All cached artefacts live under `data/valuation/`.
"""
from ..config import DATA_DIR
from .model import (
    Card,
    SetOdds,
    Valuation,
    Weights,
    DEFAULT_WEIGHTS,
    demand_weight,
    evaluate_set,
    pull_rate,
)

VALUATION_DIR = DATA_DIR / "valuation"
APITCG_CACHE_DIR = VALUATION_DIR / "apitcg"      # raw per-set dumps (regenerable)
OPTCG_CARDS = VALUATION_DIR / "optcg_cards.json"  # consolidated rarity catalog

__all__ = [
    "Card",
    "SetOdds",
    "Valuation",
    "Weights",
    "DEFAULT_WEIGHTS",
    "demand_weight",
    "evaluate_set",
    "pull_rate",
    "VALUATION_DIR",
    "APITCG_CACHE_DIR",
    "OPTCG_CARDS",
]
