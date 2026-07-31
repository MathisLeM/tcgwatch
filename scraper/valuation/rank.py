"""Over/under-valuation ranking — data-driven calibration on real prices.

Assembles one row per tracked *printing* (base SR/SEC/SP/R + every alt-art) from
the Limitless card source, joins the Limitless-meta playability signal, and
computes each printing's **pull rate** from the user-sourced odds. Then fits a
log-log regression of price on the value drivers:

    ln(price) ~ 1 + ln(pull_rate) + play_score + is_alt

The market's own weights come out of the fit; the **residual is the mispricing
signal**: price above the model → overvalued (speculative), below → undervalued
(opportunity). This needs no arbitrary box price — the set's real prices anchor it.

    python -m scraper.valuation.rank OP15 OP16          # rank across these sets
    python -m scraper.valuation.rank --all              # every built set
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass

import numpy as np

from .cards_limitless import load_cards
from .odds import distinct_in_tiers, pull_rate, version_tier
from .playability import load_playability
from .popularity import popularity_score

_KIND_SUFFIX = {"aa": " (alt)", "manga": " (manga)", "special": " (SP)"}


@dataclass
class Unit:
    code: str
    label: str
    set_code: str
    tier: str
    base_rarity: str
    is_alt: bool
    price: float
    play: float
    pull: float
    pop: float = 0.0
    fair: float = 0.0
    signal: float = 0.0     # signed % gap (price vs model), + = overvalued


def _units(sets: list[str] | None) -> list[Unit]:
    cards = load_cards()
    play = load_playability()
    all_sets = sorted({c["set_code"] for c in cards.values()})
    sets = [s.upper() for s in sets] if sets else all_sets
    distinct = {s: distinct_in_tiers(list(cards.values()), s) for s in sets}

    units: list[Unit] = []
    for c in cards.values():
        if c["set_code"] not in sets:
            continue
        pscore = play.get(c["code"], {}).get("play_score", 0.0)
        pop = popularity_score(c.get("name", ""))
        dist = distinct[c["set_code"]]
        # One unit per printing. Same-suffix duplicates (two "aa": normal parallel
        # + a rarer godpack/red-letter) can't be told apart from Limitless labels,
        # so they share a tier by default; the curated version_overrides.json tags
        # true godpacks with their own kind so the model prices them separately.
        for v in c.get("versions", []):
            tier = version_tier(c["rarity"], v["kind"], c.get("type"))
            if not tier or not v.get("eur"):
                continue
            label = c["code"] + _KIND_SUFFIX.get(v["kind"], f" ({v['kind']})" if v["kind"] != "base" else "")
            units.append(Unit(
                c["code"], label, c["set_code"], tier, c["rarity"], v["kind"] != "base",
                float(v["eur"]), pscore, pull_rate(tier, dist.get(tier, 1)), pop=pop))
    return [u for u in units if u.price > 0]


def _design(units: list[Unit]) -> tuple[np.ndarray, np.ndarray]:
    """Build the regression design matrix X and target y=ln(price).

    Model: price is explained by the card's TIER (supply regime), base RARITY
    (a leader/SEC alt beats an SR alt) and SET (hype/recency) baselines, plus
    playability and popularity. The residual is mispricing vs comparable cards.
    ln(pull) is dropped: collinear with tier+set (pull = rate(tier)·distinct(set)).
    """
    tiers = sorted({u.tier for u in units})
    set_list = sorted({u.set_code for u in units})
    rars = sorted({u.base_rarity for u in units})
    t_ix = {t: i for i, t in enumerate(tiers)}
    s_ix = {s: i for i, s in enumerate(set_list)}
    r_ix = {r: i for i, r in enumerate(rars)}

    def _dummies(ix: dict, key: str) -> list[float]:
        d = [0.0] * (len(ix) - 1)
        if ix[key] > 0:                            # drop first level (baseline)
            d[ix[key] - 1] = 1.0
        return d

    def row(u: Unit) -> list[float]:
        return [1.0, u.play, u.pop, *_dummies(t_ix, u.tier),
                *_dummies(r_ix, u.base_rarity), *_dummies(s_ix, u.set_code)]

    y = np.array([math.log(u.price) for u in units])
    X = np.array([row(u) for u in units])
    return X, y


def rank(sets: list[str] | None = None, *, over_th: float = 40.0, under_th: float = -30.0):
    """Fit the model and return (ranked_units, stats). Ranked by signal desc."""
    units = _units(sets)
    if len(units) < 8:
        raise SystemExit(f"only {len(units)} priced units — build more sets first "
                         f"(python -m scraper.valuation.cards_limitless <SETS>)")

    X, y = _design(units)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    resid = y - yhat
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

    for u, yh in zip(units, yhat):
        u.fair = math.exp(yh)
        u.signal = (u.price / u.fair - 1.0) * 100.0

    units.sort(key=lambda u: -u.signal)
    stats = {"n": len(units), "r2": r2, "play_beta": float(beta[1]),
             "pop_beta": float(beta[2]), "over_th": over_th, "under_th": under_th}
    return units, stats


def _verdict(sig: float, over: float, under: float) -> str:
    return "SURÉVALUÉE" if sig >= over else "sous-évaluée" if sig <= under else "juste"


def cross_validate(sets: list[str] | None = None, *, k: int = 5, seed: int = 0) -> dict:
    """K-fold cross-validation: does the model predict *unseen* cards?

    Fits on k-1 folds, predicts the held-out fold, and aggregates the
    out-of-sample residuals. Compares to the in-sample fit to expose overfitting.
    """
    from scipy.stats import spearmanr

    units = _units(sets)
    X, y = _design(units)
    n = len(y)
    rng = np.random.default_rng(seed)
    folds = rng.permutation(n) % k

    oos = np.zeros(n)
    for f in range(k):
        tr, te = folds != f, folds == f
        beta, *_ = np.linalg.lstsq(X[tr], y[tr], rcond=None)
        oos[te] = X[te] @ beta

    # in-sample fit for the overfit gap
    beta_all, *_ = np.linalg.lstsq(X, y, rcond=None)
    ins = X @ beta_all

    def _r2(pred):
        return 1 - float(np.sum((y - pred) ** 2)) / float(np.sum((y - y.mean()) ** 2))

    abs_pct = np.abs(np.expm1(np.abs(y - oos)))   # |predicted/actual - 1| per card
    return {
        "n": n, "k": k,
        "r2_in": _r2(ins),
        "r2_oos": _r2(oos),
        "spearman_oos": float(spearmanr(np.exp(oos), np.exp(y)).statistic),
        "median_abs_pct": float(np.median(abs_pct)) * 100,
        "p90_abs_pct": float(np.percentile(abs_pct, 90)) * 100,
    }


def _main() -> None:
    try:                                    # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description="Rank OPTCG cards over/under-valued.")
    ap.add_argument("sets", nargs="*", help="set codes (default: all built sets)")
    ap.add_argument("--all", action="store_true", help="use every built set")
    ap.add_argument("--top", type=int, default=12, help="rows per side")
    ap.add_argument("--min-price", type=float, default=5.0,
                    help="only display cards at/above this € price (speculation-relevant)")
    ap.add_argument("--cv", type=int, metavar="K", nargs="?", const=5, default=None,
                    help="run K-fold cross-validation (out-of-sample) instead of ranking")
    args = ap.parse_args()

    sel = None if args.all or not args.sets else args.sets
    if args.cv:
        cv = cross_validate(sel, k=args.cv)
        print(f"Validation croisée {cv['k']}-fold  |  n={cv['n']}")
        print(f"  R² in-sample : {cv['r2_in']:.3f}")
        print(f"  R² hors-échantillon : {cv['r2_oos']:.3f}   (écart = surapprentissage)")
        print(f"  Spearman(prédit, réel) OOS : {cv['spearman_oos']:.3f}   (qualité du classement)")
        print(f"  Erreur médiane |prix modèle vs réel| : {cv['median_abs_pct']:.0f}%   "
              f"(p90 {cv['p90_abs_pct']:.0f}%)")
        return

    units, st = rank(sel)
    print(f"Modèle: ln(prix) ~ tier + set + {st['play_beta']:.2f}·play "
          f"+ {st['pop_beta']:.2f}·pop   | n={st['n']}  R²={st['r2']:.2f}   "
          f"(résidu = sur/sous-évaluation vs pairs)")
    print(f"Affichage: cartes ≥ {args.min_price:.0f}€\n")

    shown = [u for u in units if u.price >= args.min_price]

    def show(title, rows):
        print(title)
        print(f"  {'carte':16} {'tier':5} {'prix€':>8} {'modèle€':>8} {'signal':>8}  play")
        for u in rows:
            print(f"  {u.label:16} {u.tier:5} {u.price:8.2f} {u.fair:8.2f} "
                  f"{u.signal:+7.0f}%  {u.play:.2f}")

    show("── Top SURÉVALUÉES (spéculatif / à vendre) ──", shown[:args.top])
    print()
    show("── Top SOUS-ÉVALUÉES (opportunités) ──", list(reversed(shown[-args.top:])))


if __name__ == "__main__":
    _main()
