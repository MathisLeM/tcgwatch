"""Exploratory data analysis for the valuation model — LOCAL ONLY.

Not wired into the API/dashboard. Generates PNG charts + prints validation stats
so we can sanity-check (or refute) the model on real data:

  * pull cost vs market price  — is a card's price tied to how expensive it is to
    open? (pull_cost = pull_rate packs × pack price)
  * model fair value vs actual price — how well the regression fits.
  * Spearman correlations of price with each feature (pull, pop, play).
  * per-tier "recovery" = median price / pull_cost (what fraction of open-EV the
    single trades at).

    python -m scraper.valuation.analysis            # all built sets, pack=4€
    python -m scraper.valuation.analysis --pack 3 OP15 OP16
"""
from __future__ import annotations

import argparse
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
from scipy.stats import spearmanr        # noqa: E402

from . import VALUATION_DIR              # noqa: E402
from .rank import rank                   # noqa: E402

ANALYSIS_DIR = VALUATION_DIR / "analysis"
_TIER_COLOR = {
    "R": "#9aa0a6", "SR": "#4c8bf5", "SEC": "#a142f4", "SP": "#f4b400",
    "alt": "#0f9d58", "manga": "#db4437", "special": "#ff6d00",
}


def _scatter_by_tier(ax, xs, ys, tiers, xlabel, ylabel, title):
    for tier in sorted(set(tiers)):
        idx = [i for i, t in enumerate(tiers) if t == tier]
        ax.scatter([xs[i] for i in idx], [ys[i] for i in idx], s=18, alpha=0.7,
                   color=_TIER_COLOR.get(tier, "#333"), label=tier, edgecolors="none")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, which="both", ls=":", alpha=0.3)
    ax.legend(fontsize=8, framealpha=0.9)


def run(sets: list[str] | None, pack_price: float) -> None:
    units, st = rank(sets)
    price = np.array([u.price for u in units])
    pull = np.array([u.pull for u in units])
    pull_cost = pull * pack_price
    pop = np.array([u.pop for u in units])
    play = np.array([u.play for u in units])
    fair = np.array([u.fair for u in units])
    tiers = [u.tier for u in units]

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) pull cost vs price
    fig, ax = plt.subplots(figsize=(8, 6))
    _scatter_by_tier(ax, pull_cost, price, tiers,
                     f"coût d'ouverture (pull_rate × {pack_price:.0f}€/pack)  [€, log]",
                     "prix marché [€, log]", "Pull cost vs prix marché")
    lim = [min(pull_cost.min(), price.min()) * 0.8, max(pull_cost.max(), price.max()) * 1.2]
    ax.plot(lim, lim, "k--", lw=1, alpha=0.6, label="prix = coût d'ouverture")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "pullcost_vs_price.png", dpi=110)
    plt.close(fig)

    # 2) model fair value vs actual price (fit quality)
    fig, ax = plt.subplots(figsize=(8, 6))
    _scatter_by_tier(ax, fair, price, tiers, "prix modèle (fair) [€, log]",
                     "prix marché [€, log]", f"Modèle vs marché — R²={st['r2']:.2f}")
    lim = [min(fair.min(), price.min()) * 0.8, max(fair.max(), price.max()) * 1.2]
    ax.plot(lim, lim, "k--", lw=1, alpha=0.6)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "model_vs_market.png", dpi=110)
    plt.close(fig)

    # 3) price vs each raw feature
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    _scatter_by_tier(axes[0], pull, price, tiers, "pull_rate [packs, log]", "prix [€, log]", "prix vs rareté (pull)")
    axes[1].scatter(pop, price, s=16, alpha=0.6, c="#4c8bf5"); axes[1].set_yscale("log")
    axes[1].set_xlabel("popularité perso (0-1)"); axes[1].set_ylabel("prix [€, log]")
    axes[1].set_title("prix vs popularité"); axes[1].grid(True, ls=":", alpha=0.3)
    axes[2].scatter(play, price, s=16, alpha=0.6, c="#0f9d58"); axes[2].set_yscale("log")
    axes[2].set_xlabel("jouabilité (0-3)"); axes[2].set_ylabel("prix [€, log]")
    axes[2].set_title("prix vs jouabilité"); axes[2].grid(True, ls=":", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "price_vs_features.png", dpi=110)
    plt.close(fig)

    # ── validation stats ─────────────────────────────────────────────────────
    try:                                    # Windows console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    lp = np.log(price)
    print(f"n={len(units)}  sets={sorted(set(u.set_code for u in units))}  R²(modèle)={st['r2']:.2f}")
    print("\nCorrélations de Spearman (prix vs feature):")
    for name, x in [("pull_rate", pull), ("pull_cost", pull_cost), ("popularité", pop), ("jouabilité", play)]:
        rho, p = spearmanr(price, x)
        print(f"  {name:12} rho={rho:+.2f}  (p={p:.1e})")

    print("\nRecovery = prix / coût d'ouverture, par tier (médiane):")
    for tier in sorted(set(tiers)):
        idx = [i for i, t in enumerate(tiers) if t == tier]
        rec = price[idx] / pull_cost[idx]
        print(f"  {tier:8} n={len(idx):3}  médiane={np.median(rec):6.1%}  "
              f"[{np.percentile(rec,25):.1%}–{np.percentile(rec,75):.1%}]")

    print(f"\nCharts -> {ANALYSIS_DIR}")


def _main() -> None:
    ap = argparse.ArgumentParser(description="Local EDA for the valuation model (no dashboard).")
    ap.add_argument("sets", nargs="*", help="set codes (default: all built)")
    ap.add_argument("--pack", type=float, default=4.0, help="booster pack price € (default 4)")
    args = ap.parse_args()
    run(args.sets or None, args.pack)


if __name__ == "__main__":
    _main()
