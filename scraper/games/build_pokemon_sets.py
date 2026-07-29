"""Build the Pokemon set reference (SWSH-era -> present) from TCGdex.

For every tracked language it pulls the full set list, fetches each set's detail
to get the release date + series, keeps sets released on/after MIN_RELEASE, and
writes:
  - data/reference/pokemon_sets.json   (cached reference, consumed by games/pokemon.py)
  - the `sets` table in the DB          (game='pokemon')

Run:  python -m scraper.games.build_pokemon_sets
"""
import json
import time
import datetime as dt
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..config import REFERENCE_DIR, USER_AGENT
from ..db import connect, init_db

API = "https://api.tcgdex.net/v2"
MIN_RELEASE = "2020-01-01"   # Sword & Shield era onward
# TCGdex source language -> our language code. Chinese: merge tw + cn into 'zh'.
SOURCE_LANGS = {"en": "en", "fr": "fr", "ja": "ja", "ko": "ko",
                "zh-tw": "zh", "zh-cn": "zh"}
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _get(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(2 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(1)
    return None


def _set_detail(src_lang, set_id):
    d = _get(f"{API}/{src_lang}/sets/{set_id}")
    if not d:
        return None
    rd = d.get("releaseDate")
    if not rd or rd < MIN_RELEASE:
        return None
    serie = d.get("serie") or {}
    cc = d.get("cardCount") or {}
    abbr = (d.get("abbreviation") or {}).get("official")
    return {
        "set_code": d["id"],
        "name": d.get("name"),
        "abbreviation": abbr,
        "series": serie.get("id"),
        "release_date": rd,
        "logo_url": (d.get("logo") + ".png") if d.get("logo") else None,
        "symbol_url": (d.get("symbol") + ".png") if d.get("symbol") else None,
        "card_count": cc.get("official") or cc.get("total"),
    }


def fetch_lang(src_lang):
    """Return list of modern-era set rows for one TCGdex language."""
    resume = _get(f"{API}/{src_lang}/sets")
    if not resume:
        print(f"  {src_lang:<6} list ERROR")
        return []
    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(_set_detail, src_lang, s["id"]): s["id"] for s in resume}
        for fut in as_completed(futs):
            d = fut.result()
            if d:
                rows.append(d)
    print(f"  {src_lang:<6} {len(rows):>3} sets >= {MIN_RELEASE}  (of {len(resume)})")
    return rows


def build():
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    # lang -> {set_code: row} so 'zh' merge (tw preferred) dedupes naturally.
    by_lang = {}
    for src_lang, lang in SOURCE_LANGS.items():
        dest = by_lang.setdefault(lang, {})
        for row in fetch_lang(src_lang):
            row["language"] = lang
            row["game"] = "pokemon"
            # zh: prefer zh-tw (processed first) — don't overwrite with zh-cn.
            dest.setdefault(row["set_code"], row)

    sets = [r for rows in by_lang.values() for r in rows.values()]
    out = {
        "built_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_release": MIN_RELEASE,
        "source_langs": SOURCE_LANGS,
        "count": len(sets),
        "sets": sets,
    }
    ref_path = REFERENCE_DIR / "pokemon_sets.json"
    ref_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(sets)} set rows -> {ref_path}")

    # Upsert into the DB `sets` table.
    init_db()
    with connect() as conn:
        conn.executemany("""
            INSERT INTO sets (game, language, set_code, name, abbreviation, series, release_date,
                              logo_url, symbol_url, card_count)
            VALUES (:game, :language, :set_code, :name, :abbreviation, :series, :release_date,
                    :logo_url, :symbol_url, :card_count)
            ON CONFLICT(game, language, set_code) DO UPDATE SET
                name=excluded.name, abbreviation=excluded.abbreviation, series=excluded.series,
                release_date=excluded.release_date, logo_url=excluded.logo_url,
                symbol_url=excluded.symbol_url, card_count=excluded.card_count
        """, sets)
        conn.commit()
        by = conn.execute("""
            SELECT language, COUNT(*) FROM sets WHERE game='pokemon'
            GROUP BY language ORDER BY language
        """).fetchall()
    print("\nDB sets by language:")
    for lang, c in by:
        print(f"  {lang:<4} {c}")


if __name__ == "__main__":
    build()
