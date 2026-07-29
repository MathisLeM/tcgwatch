"""Cardmarket sealed-product reference.

Cardmarket's "non-singles" product dump lists every sealed product it catalogs,
tagged with a product category (Booster / Display / ETB / Tins / Blisters / Box
Set ...) and an `idExpansion` (but no expansion name and no language). We use it
to answer: **which product kinds exist for each set?**

How it maps to our model:
- Each expansion's set name is derived from its Display/Booster/ETB product name
  (e.g. "Sword & Shield Darkness Ablaze Booster Box" -> "darkness ablaze"), with
  the series prefix stripped, then matched to our TCGdex **en** set names by
  token-subset. Western set codes (sv*, swsh*) are shared across en/fr/de/..., so
  the result applies to the Western languages we track (en + fr).
- Cardmarket has no language field; it does not cover JP/KO/ZH-specific sets, so
  those are left to the per-language baseline / live scraping.

Public API:
  set_kinds() -> {set_code: sorted[kind]}   # Western sealed sets only
  report()                                  # print coverage + write an Excel
"""
import json
import re
import unicodedata
import collections
from functools import lru_cache
from ..config import REFERENCE_DIR

PRODUCTS_FILE = REFERENCE_DIR / "cardmarket" / "products_nonsingles_pokemon.json"

# Cardmarket categoryName -> our catalog kind (simple 1:1 cases).
_CAT_KIND = {
    "Pokémon Booster": "booster",
    "Pokémon Display": "display",
    "Pokémon Elite Trainer Boxes": "etb",
    "Pokémon Blisters": "blister",
}
# Categories needing per-product sub-classification by name.
_CAT_SUBCLASS = {"Pokémon Tins", "Pokémon Box Set"}
# Priority for picking the product we derive the expansion's set name from.
_NAME_PRIORITY = {"Pokémon Display": 0, "Pokémon Booster": 1,
                  "Pokémon Elite Trainer Boxes": 2, "Pokémon Box Set": 3,
                  "Pokémon Tins": 4, "Pokémon Blisters": 5}
_SUFFIXES = ["booster box", "booster", "elite trainer box",
             "build and battle stadium", "build and battle box"]
_SERIES_PREFIX = ["scarlet and violet", "sword and shield", "sun and moon",
                  "black and white", "x and y", "sv", "swsh"]


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _strip_prefix(name: str) -> str:
    s = re.sub(r"\s+", " ", name).strip()
    for p in _SERIES_PREFIX:
        if s.startswith(p + " "):
            s = s[len(p) + 1:]
    return s.strip()


def _subclass(category: str, name_norm: str) -> str:
    if category == "Pokémon Tins":
        return "minitin" if "mini tin" in name_norm else "coffret"
    # Box Set: premium collections, bundles, UPCs, generic collections.
    if "ultra premium" in name_norm:
        return "upc"
    if "bundle" in name_norm:
        return "bundle"
    return "coffret"


def _kind_for(category: str, name_norm: str) -> str | None:
    if category in _CAT_KIND:
        return _CAT_KIND[category]
    if category in _CAT_SUBCLASS:
        return _subclass(category, name_norm)
    return None


@lru_cache(maxsize=1)
def _parse():
    """Return (exp_kinds, exp_name_tokens): kinds + derived set-name tokens per idExpansion."""
    data = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    exp_kinds = collections.defaultdict(set)
    best_name = {}   # idExpansion -> (priority, set_of_tokens)
    for p in data.get("products", []):
        cat = p.get("categoryName", "")
        e = p.get("idExpansion")
        nm_norm = _norm(p.get("name", ""))
        kind = _kind_for(cat, nm_norm)
        if kind:
            exp_kinds[e].add(kind)
        if cat in _NAME_PRIORITY:
            nm = nm_norm
            for suf in _SUFFIXES:
                if nm.endswith(" " + suf):
                    nm = nm[: -len(suf) - 1]
                    break
            toks = frozenset(_strip_prefix(nm).split())
            pr = _NAME_PRIORITY[cat]
            if toks and (e not in best_name or pr < best_name[e][0]):
                best_name[e] = (pr, toks)
    exp_tokens = {e: v[1] for e, v in best_name.items()}
    return dict(exp_kinds), exp_tokens


@lru_cache(maxsize=1)
def _tcgdex_en_sealed():
    """[(set_code, token_set)] for our en sets, excluding TCG Pocket (digital)."""
    ref = json.loads((REFERENCE_DIR / "pokemon_sets.json").read_text(encoding="utf-8"))["sets"]
    out = []
    for r in ref:
        if r["language"] == "en" and r.get("series") != "tcgp":
            toks = frozenset(_strip_prefix(_norm(r["name"])).split())
            out.append((r["set_code"], toks))
    return out


def _match_expansion(set_tokens):
    """Return idExpansion whose derived name best matches a set's tokens, or None."""
    _, exp_tokens = _parse()
    cands = []
    for e, C in exp_tokens.items():
        if not set_tokens:
            continue
        if set_tokens <= C:          # cardmarket name contains all our tokens
            cands.append((len(C - set_tokens), e))
        elif C <= set_tokens:        # our name contains all cardmarket tokens
            cands.append((len(set_tokens - C) + 0.5, e))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])
    return cands[0][1]


@lru_cache(maxsize=1)
def set_kinds() -> dict:
    """{set_code: sorted[kind]} for Western sealed sets present on Cardmarket.

    Multiple Cardmarket expansions can map to one set (e.g. an EN and a promo
    expansion); their kinds are unioned.
    """
    exp_kinds, _ = _parse()
    out = collections.defaultdict(set)
    for code, toks in _tcgdex_en_sealed():
        e = _match_expansion(toks)
        if e is not None:
            out[code] |= exp_kinds.get(e, set())
    return {code: sorted(ks) for code, ks in out.items() if ks}


def report():
    """Print coverage and write data/reference/cardmarket/set_product_types.xlsx."""
    import pandas as pd
    sk = set_kinds()
    sealed = _tcgdex_en_sealed()
    ref = json.loads((REFERENCE_DIR / "pokemon_sets.json").read_text(encoding="utf-8"))["sets"]
    name_by_code = {r["set_code"]: r["name"] for r in ref if r["language"] == "en"}
    date_by_code = {r["set_code"]: r["release_date"] for r in ref if r["language"] == "en"}
    all_kinds = ["display", "etb", "upc", "bundle", "blister", "coffret", "minitin", "booster"]

    rows = []
    for code, _ in sorted(sealed, key=lambda t: date_by_code.get(t[0]) or ""):
        ks = sk.get(code)
        rec = {"set_code": code, "name": name_by_code.get(code, code),
               "release_date": date_by_code.get(code),
               "on_cardmarket": "yes" if ks else "no"}
        for k in all_kinds:
            rec[k] = "x" if ks and k in ks else ""
        rows.append(rec)
    df = pd.DataFrame(rows)
    out = REFERENCE_DIR / "cardmarket" / "set_product_types.xlsx"
    df.to_excel(out, index=False)
    matched = sum(1 for r in rows if r["on_cardmarket"] == "yes")
    print(f"Cardmarket sealed coverage: {matched}/{len(rows)} sealed en sets matched")
    print(f"Wrote {out}")


if __name__ == "__main__":
    report()
