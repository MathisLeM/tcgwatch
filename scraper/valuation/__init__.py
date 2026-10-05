"""Card fair-value / speculation model (OPTCG to start).

Two layers:
  - `model` — the pure over/under-valuation math (demand/supply, pull rate,
    value-conserving normalisation). No I/O, no network.
  - data adapters that feed it real features (all keyless):
      * `cards_limitless` — rarity, per-version EUR price, alt identity (Limitless).
      * `playability`     — share-weighted metagame usage (Limitless).
      * `popularity`      — character rank from the WT100 reader poll.
      * `odds`            — user-sourced pull rates per tier.
  - `rank` fits the regression and ranks over/under-valued printings.

The former apitcg rarity source lives in `scraper.legacy.apitcg_rarity`.

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
]
