"""Build the Pokemon navigation hierarchy: **block > set > article type**.

Turns the flat TCGdex set reference + the scraped `products` table into a nested
structure that makes the catalogue easy to browse:

    Block  (Méga-Évolution, Écarlate et Violet, Épée et Bouclier, ...)
     └─ Set   (Étincelles Déferlantes [PRE], 151 [EV3.5], ...)
         └─ Article type (Display, ETB, Coffret, Booster, Bundle, ...)

Each level carries its images, localized names and a live product count (how many
tracked shop listings fall under it), so the frontend can render a drill-down and
so a human can sanity-check coverage from the Excel export.

Outputs:
  - data/reference/pokemon_hierarchy.json   (consumed by the API / frontend)
  - data/reference/pokemon_hierarchy.xlsx   (flat, hand-reviewable listing)

The same `build_hierarchy()` is reused by the API (`/sets/blocks`) so the site
and this offline export never drift apart.

Run:  python -m scraper.games.pokemon_hierarchy [--language fr]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections import defaultdict

from ..config import REFERENCE_DIR, ROOT
from . import pokemon

JSON_OUT = REFERENCE_DIR / "pokemon_hierarchy.json"
XLSX_OUT = REFERENCE_DIR / "pokemon_hierarchy.xlsx"

# Product counts keyed by (language, set_code, kind); catalogue kinds by (language, set_code).
Counts = dict
CountKey = tuple


def _rel(path: str | None) -> str | None:
    """Project-root-relative, forward-slash image path (portable in JSON), or None."""
    if not path:
        return None
    try:
        return os.path.relpath(path, ROOT).replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def _set_number(set_code: str) -> str:
    import re
    m = re.search(r"(\d+(?:\.\d+)?)$", set_code or "")
    return m.group(1) if m else ""


def build_hierarchy(product_counts: dict | None = None,
                    languages: list[str] | None = None) -> dict:
    """Return the nested block > set > article-type structure.

    `product_counts`: {(language, set_code, kind): n} of tracked listings. When
    omitted the hierarchy is the pure reference catalogue (every count 0).
    `languages`: restrict to these language codes (default: all tracked).
    """
    product_counts = product_counts or {}
    languages = languages or list(pokemon.LANGUAGES)
    ref = pokemon._load_reference()
    rows = [r for r in ref["sets"] if r.get("language") in languages]

    # --- group reference sets by canonical block ---------------------------- #
    blocks: dict[str, list] = defaultdict(list)
    for r in rows:
        blocks[pokemon.canonical_block(r.get("series"))].append(r)

    block_nodes = []
    for block_id, set_rows in blocks.items():
        if not block_id:
            continue
        set_nodes = []
        for r in sorted(set_rows, key=lambda x: (x.get("release_date") or "", x["set_code"])):
            lang, code = r["language"], r["set_code"]
            # article types actually tracked for this (language, set)
            kinds = []
            for kind in pokemon.KIND_ORDER:
                n = product_counts.get((lang, code, kind), 0)
                if n:
                    kinds.append({"kind": kind, "label": pokemon.kind_label(kind, "fr"),
                                  "label_en": pokemon.kind_label(kind, "en"),
                                  "product_count": n})
            set_pc = sum(k["product_count"] for k in kinds)
            set_nodes.append({
                "language": lang,
                "set_code": code,
                "abbreviation": r.get("abbreviation") or pokemon.abbreviation_of(code),
                "number": _set_number(code),
                "name": r.get("name") or code,
                "release_date": r.get("release_date"),
                "card_count": r.get("card_count"),
                "image": _rel(pokemon.series_image(code)),
                "logo_url": r.get("logo_url"),
                "block": block_id,
                "product_count": set_pc,
                "kinds": kinds,
            })
        # Newest sets first within a block; sets with listings ahead of empty ones.
        set_nodes.sort(key=lambda s: (s["release_date"] or ""), reverse=True)
        dates = [s["release_date"] for s in set_nodes if s["release_date"]]
        block_nodes.append({
            "block": block_id,
            "block_code": pokemon.block_code(block_id),
            "name": {"fr": pokemon.series_name(block_id, "fr"),
                     "en": pokemon.series_name(block_id, "en")},
            "image": _rel(pokemon.block_image(block_id)),
            "release_start": min(dates) if dates else None,
            "release_end": max(dates) if dates else None,
            "set_count": len(set_nodes),
            "product_count": sum(s["product_count"] for s in set_nodes),
            "sets": set_nodes,
        })

    block_nodes.sort(key=lambda b: pokemon.block_sort_key(b["block"], b["release_end"] or ""))

    # --- setless / unassigned tracked listings (old sets, standalone tins) --- #
    unassigned = []
    for (lang, code, kind), n in product_counts.items():
        if code:
            continue
        unassigned.append((lang, kind, n))
    unassigned_kinds = defaultdict(int)
    for lang, kind, n in unassigned:
        unassigned_kinds[kind] += n
    unassigned_node = {
        "product_count": sum(unassigned_kinds.values()),
        "kinds": [{"kind": k, "label": pokemon.kind_label(k, "fr"), "product_count": v}
                  for k, v in sorted(unassigned_kinds.items(), key=lambda kv: -kv[1])],
    }

    return {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "languages": languages,
        "block_count": len(block_nodes),
        "blocks": block_nodes,
        "unassigned": unassigned_node,
    }


# --------------------------------------------------------------------------- #
# Offline build (reads counts from the local SQLite DB)
# --------------------------------------------------------------------------- #
def _counts_from_db() -> dict:
    """{(language, set_code, kind): n_products} for game='pokemon' from SQLite."""
    from ..db import connect
    counts = {}
    with connect() as conn:
        for r in conn.execute("""
            SELECT language, COALESCE(set_code, '') AS set_code,
                   COALESCE(kind, 'unknown') AS kind, COUNT(*) AS n
            FROM products WHERE game='pokemon'
            GROUP BY language, set_code, kind
        """):
            counts[(r["language"], r["set_code"], r["kind"])] = r["n"]
    return counts


def _to_dataframe(hierarchy: dict):
    import pandas as pd
    rows = []
    for b in hierarchy["blocks"]:
        for s in b["sets"]:
            if s["kinds"]:
                for k in s["kinds"]:
                    rows.append({
                        "block": b["block_code"], "block_name": b["name"]["fr"],
                        "set_code": s["set_code"], "language": s["language"],
                        "abbreviation": s["abbreviation"], "number": s["number"],
                        "set_name": s["name"], "release_date": s["release_date"],
                        "has_image": bool(s["image"]),
                        "kind": k["kind"], "article_type": k["label"],
                        "product_count": k["product_count"],
                    })
            else:
                rows.append({
                    "block": b["block_code"], "block_name": b["name"]["fr"],
                    "set_code": s["set_code"], "language": s["language"],
                    "abbreviation": s["abbreviation"], "number": s["number"],
                    "set_name": s["name"], "release_date": s["release_date"],
                    "has_image": bool(s["image"]),
                    "kind": "", "article_type": "", "product_count": 0,
                })
    return pd.DataFrame(rows)


def build(languages: list[str] | None = None) -> dict:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    counts = _counts_from_db()
    hierarchy = build_hierarchy(counts, languages=languages)
    JSON_OUT.write_text(json.dumps(hierarchy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {JSON_OUT}")

    df = _to_dataframe(hierarchy)
    df.to_excel(XLSX_OUT, index=False)
    print(f"Wrote {XLSX_OUT}  ({len(df)} rows)")

    print("\n=== Blocks (newest era first) ===")
    for b in hierarchy["blocks"]:
        img = "img" if b["image"] else "no-img"
        print(f"  {b['block_code']:5} {b['name']['fr']:<26} "
              f"sets={b['set_count']:>3}  listings={b['product_count']:>4}  [{img}]")
    u = hierarchy["unassigned"]
    print(f"\n  Setless listings (old sets / standalone tins): {u['product_count']}")
    return hierarchy


def main():
    ap = argparse.ArgumentParser(description="Build the Pokemon block>set>type hierarchy.")
    ap.add_argument("--language", action="append", dest="languages",
                    help="Restrict to a language (repeatable). Default: all.")
    args = ap.parse_args()
    build(languages=args.languages)


if __name__ == "__main__":
    main()
