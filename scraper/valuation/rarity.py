"""Rarity / alt-art catalog for OPTCG cards — keyless source.

Pulls per-set card data from the public **apitcg/one-piece-tcg-data** GitHub
mirror (same data as API TCG, no key needed) and consolidates it into a single
`code -> {rarity, name, type, ...}` catalog cached at `data/valuation/optcg_cards.json`.

Each raw entry is one *printing*: `code` is the card identity (e.g. `OP09-051`)
and `id` adds a parallel suffix for alt arts (`OP09-051_p1`, `..._p2`). We keep
the base printing's rarity and record how many parallels exist, so downstream
valuation can flag alt-art premiums.

    from scraper.valuation.rarity import build_catalog, load_catalog
    build_catalog()                 # download + consolidate (cached on disk)
    cards = load_catalog()          # {code: {...}}  read-only

CLI:
    python -m scraper.valuation.rarity              # build (uses cache if present)
    python -m scraper.valuation.rarity --refresh    # re-download every set
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict

from . import APITCG_CACHE_DIR, OPTCG_CARDS, VALUATION_DIR

RAW_BASE = "https://raw.githubusercontent.com/apitcg/one-piece-tcg-data/main/cards/en"
INDEX_API = "https://api.github.com/repos/apitcg/one-piece-tcg-data/contents/cards/en"
_UA = {"User-Agent": "TCGWatch/1.0 (+valuation catalog build)"}

# Sets that actually come from booster boxes (pull-rate meaningful). Starter
# decks (ST*) have fixed contents, `general` holds promos — kept for the price
# join / rarity lookup, but flagged so the pull-rate model can skip them.
_BOOSTER_RE = re.compile(r"^(op|eb|prb)\d*$", re.I)
_PARALLEL_RE = re.compile(r"_p\d+$", re.I)          # id suffix marking an alt art

# Canonical rarity buckets (raw strings from the source on the left).
RARITY_CANON = {
    "C": "C", "UC": "UC", "R": "R", "SR": "SR", "SEC": "SEC", "L": "L",
    "SP CARD": "SP", "SP": "SP", "P": "P", "PROMO": "P", "TR": "TR", "DON!!": "DON",
}


def canon_rarity(raw: str | None) -> str:
    if not raw:
        return "?"
    return RARITY_CANON.get(raw.strip().upper(), raw.strip().upper())


def _get(url: str, *, as_json: bool = True):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data) if as_json else data


def list_set_files(*, boosters_only: bool = False) -> list[str]:
    """Filenames (e.g. 'op09.json') available in the source's cards/en folder."""
    files = [it["name"] for it in _get(INDEX_API) if it["name"].endswith(".json")]
    if boosters_only:
        files = [f for f in files if _BOOSTER_RE.match(f[:-5])]
    return sorted(files)


def _fetch_set(filename: str, *, refresh: bool = False) -> list[dict]:
    """Raw card list for one set file, cached under data/valuation/apitcg/."""
    APITCG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = APITCG_CACHE_DIR / filename
    if cached.exists() and not refresh:
        return json.loads(cached.read_text(encoding="utf-8"))
    rows = _get(f"{RAW_BASE}/{filename}")
    cached.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def consolidate(raw_by_file: dict[str, list[dict]]) -> dict[str, dict]:
    """Pure aggregation: raw apitcg rows (keyed by set filename slug, no `.json`)
    -> a `code -> info` catalog. No I/O — unit-testable."""
    variants: dict[str, list[dict]] = defaultdict(list)
    for slug, rows in raw_by_file.items():
        for row in rows:
            code = (row.get("code") or "").strip().upper()
            if not code:
                continue
            variants[code].append({
                "id": row.get("id") or code,
                "rarity": canon_rarity(row.get("rarity")),
                "set": (row.get("set") or {}).get("name"),
                "set_file": slug.upper(),
                "name": row.get("name"),
                "type": row.get("type"),
                "color": row.get("color"),
                "family": row.get("family"),
                "cost": row.get("cost"),
                "power": row.get("power"),
            })

    catalog: dict[str, dict] = {}
    for code, vs in variants.items():
        base = next((v for v in vs if not _PARALLEL_RE.search(v["id"])), vs[0])
        rarities = sorted({v["rarity"] for v in vs})
        parallels = [v for v in vs if _PARALLEL_RE.search(v["id"])]
        set_files = sorted({v["set_file"] for v in vs})
        catalog[code] = {
            "code": code,
            "name": base.get("name"),
            "rarity": base["rarity"],
            "rarities": rarities,          # every printing's rarity for this code
            "type": base.get("type"),
            "color": base.get("color"),
            "family": base.get("family"),
            "cost": base.get("cost"),
            "power": base.get("power"),
            "n_variants": len(vs),
            "n_parallels": len(parallels),
            "has_parallel": bool(parallels),
            "set_code": code.split("-")[0],
            "set_files": set_files,
            "from_booster": bool(_BOOSTER_RE.match(code.split("-")[0])),
        }
    return catalog


def build_catalog(*, refresh: bool = False, boosters_only: bool = False,
                  polite: float = 0.2) -> dict[str, dict]:
    """Download every mirror set, consolidate, and cache.

    Covers what the keyless GitHub mirror ships (up to ~OP12/EB02/PRB01). For the
    recent sets and per-version prices, the valuation pipeline uses
    `cards_limitless` instead. Writes `data/valuation/optcg_cards.json`.
    """
    raw_by_file: dict[str, list[dict]] = {}
    for fn in list_set_files(boosters_only=boosters_only):
        fresh = not (APITCG_CACHE_DIR / fn).exists() or refresh
        raw_by_file[fn[:-5]] = _fetch_set(fn, refresh=refresh)
        if fresh:
            time.sleep(polite)

    catalog = consolidate(raw_by_file)
    VALUATION_DIR.mkdir(parents=True, exist_ok=True)
    OPTCG_CARDS.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return catalog


def load_catalog() -> dict[str, dict]:
    """Read the consolidated catalog; build it first if missing."""
    if not OPTCG_CARDS.exists():
        return build_catalog()
    return json.loads(OPTCG_CARDS.read_text(encoding="utf-8"))


def _main() -> None:
    ap = argparse.ArgumentParser(description="Build the OPTCG rarity catalog (keyless apitcg dump).")
    ap.add_argument("--refresh", action="store_true", help="re-download every set (ignore cache)")
    ap.add_argument("--boosters-only", action="store_true", help="skip ST decks / promos")
    args = ap.parse_args()

    cat = build_catalog(refresh=args.refresh, boosters_only=args.boosters_only)
    by_rarity: dict[str, int] = defaultdict(int)
    alts = 0
    for info in cat.values():
        by_rarity[info["rarity"]] += 1
        alts += info["has_parallel"]
    print(f"Catalog: {len(cat)} cards -> {OPTCG_CARDS}")
    print(f"  with alt-art (parallel): {alts}")
    print("  by base rarity: " + ", ".join(
        f"{r}={n}" for r, n in sorted(by_rarity.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    _main()
