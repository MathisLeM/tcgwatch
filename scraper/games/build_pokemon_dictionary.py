"""Build the Pokemon categorization dictionary (multilingual set + series names).

Produces:
  - data/reference/pokemon_series.json   : {lang: {series_id: series_name}}  (TCGdex)
  - data/reference/pokemon_set_dictionary.xlsx : one row per set_code with the
    series, the number, and the name in FR/EN/JA/KO/ZH — the hand-reviewable
    vocabulary used to flag products by set.

Consumed at runtime by games/pokemon.py for set + series extraction.

Run:  python -m scraper.games.build_pokemon_dictionary
"""
import json
import re
import requests
import pandas as pd
from ..config import REFERENCE_DIR

SETS_FILE = REFERENCE_DIR / "pokemon_sets.json"
SERIES_FILE = REFERENCE_DIR / "pokemon_series.json"
DICT_XLSX = REFERENCE_DIR / "pokemon_set_dictionary.xlsx"
SRC_LANGS = {"fr": "fr", "en": "en", "ja": "ja", "ko": "ko", "zh-tw": "zh"}
LANGS = ["fr", "en", "ja", "ko", "zh"]


def fetch_series_names() -> dict:
    """{lang: {series_id: name}} from TCGdex (only fr/en are populated upstream)."""
    out = {l: {} for l in LANGS}
    for src, lang in SRC_LANGS.items():
        try:
            r = requests.get(f"https://api.tcgdex.net/v2/{src}/series", timeout=20).json()
            for s in r:
                if s.get("name"):
                    out[lang].setdefault(s["id"], s["name"])
        except Exception as e:
            print(f"  series {src}: ERROR {e}")
    return out


def set_number(set_code: str) -> str:
    """Ordinal within a series, encoded in the code: sv03.5 -> '3.5', me04 -> '4'."""
    m = re.search(r"(\d+(?:\.\d+)?)$", set_code or "")
    return m.group(1) if m else ""


def build():
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    series_names = fetch_series_names()
    SERIES_FILE.write_text(json.dumps(series_names, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {SERIES_FILE}")

    from .pokemon import block_code

    sets = json.loads(SETS_FILE.read_text(encoding="utf-8"))["sets"]
    # union set_codes across languages; keep series + release_date from any row.
    by_code = {}
    for r in sets:
        c = r["set_code"]
        d = by_code.setdefault(c, {"set_code": c, "series": r.get("series"),
                                   "release_date": r.get("release_date"),
                                   "abbreviation": r.get("abbreviation")})
        d[f"name_{r['language']}"] = r.get("name")
        d["series"] = d.get("series") or r.get("series")
        d["release_date"] = d.get("release_date") or r.get("release_date")
        d["abbreviation"] = d.get("abbreviation") or r.get("abbreviation")

    rows = []
    for c, d in by_code.items():
        ser = d.get("series") or ""
        rows.append({
            "block": block_code(ser),
            "abbreviation": d.get("abbreviation") or "",
            "series_id": ser,
            "series_fr": series_names["fr"].get(ser, ""),
            "series_en": series_names["en"].get(ser, ""),
            "number": set_number(c),
            "set_code": c,
            "release_date": d.get("release_date"),
            "name_fr": d.get("name_fr", ""),
            "name_en": d.get("name_en", ""),
            "name_ja": d.get("name_ja", ""),
            "name_ko": d.get("name_ko", ""),
            "name_zh": d.get("name_zh", ""),
        })
    cols = ["block", "abbreviation", "series_id", "series_fr", "series_en", "number",
            "set_code", "release_date", "name_fr", "name_en", "name_ja", "name_ko", "name_zh"]
    df = pd.DataFrame(rows)
    df = df[[c for c in cols if c in df.columns]].sort_values(
        ["series_id", "release_date", "set_code"])
    df.to_excel(DICT_XLSX, index=False)
    print(f"Wrote {DICT_XLSX}  ({len(df)} sets)")
    print("\nSeries (fr):")
    for sid, nm in series_names["fr"].items():
        print(f"  {sid:6} {nm}")


if __name__ == "__main__":
    build()
