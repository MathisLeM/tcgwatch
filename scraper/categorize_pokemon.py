"""Filter the raw Pokemon scrape to sealed products, auto-categorize, and load.

Reads data/discovered_pokemon_raw.xlsx, then:
  1. keeps only sealed Pokemon products (drops singles / goodies / non-Pokemon),
  2. auto-categorizes each (language + set + kind) using title + description +
     tags + collection — not just the title,
  3. writes a reviewable data/discovered_pokemon.xlsx,
  4. loads them into the DB as game='pokemon' (products + one snapshot each),
     linking catalog_id when a matching curated catalog row exists.

Run:  python -m scraper.categorize_pokemon
"""
import datetime as dt
import pandas as pd
from .config import DATA_DIR
from .db import connect, init_db
from .games import pokemon

RAW = DATA_DIR / "discovered_pokemon_raw.xlsx"
OUT = DATA_DIR / "discovered_pokemon.xlsx"


def _extra(r) -> str:
    parts = [str(r.get(c) or "") for c in ("description", "tags", "product_type", "collection", "vendor")]
    return " ".join(p for p in parts if p)


def categorize():
    if not RAW.exists():
        raise SystemExit(f"{RAW} not found. Run `python -m scraper.discover_pokemon` first.")
    df = pd.read_excel(RAW)
    print(f"Raw rows: {len(df)}")

    kept = []
    n_single_goodie = n_notpoke = 0
    for _, r in df.iterrows():
        title = str(r.get("title") or "")
        url = str(r.get("url") or "")
        extra = _extra(r)
        shop = str(r.get("shop") or "")
        # Detect language first so the (market-aware) sealed gate and kind
        # classification can use it (e.g. JA bare-'box' -> sealed display).
        lang = pokemon.detect_language(title, url, extra)
        if not pokemon.is_sealed(title, extra, language=lang, shop=shop):
            n_single_goodie += 1
            continue
        sets = pokemon.extract_sets(title, url, lang, extra)
        set_code = sets[0] if sets else ""
        blob = f"{title} {extra} {url}".lower()
        if "pokemon" not in blob and "pokémon" not in blob and not set_code:
            n_notpoke += 1
            continue
        kind = pokemon.classify_kind(title, extra=extra, language=lang)
        # Store the canonical block id (JP era ids 'SV'/'S'/'M' -> 'sv'/'swsh'/'me')
        # so products group by block consistently across languages.
        series = pokemon.canonical_block(
            pokemon.extract_series(title, url, lang, extra, set_code))
        kept.append({
            "platform": r.get("platform"), "shop": r.get("shop"),
            "platform_pid": str(r.get("platform_pid") or ""),
            "language": lang, "set": set_code, "set_codes": ";".join(sets),
            "series": series, "kind": kind,
            "title": title,
            "price_min": r.get("price_min"),
            "available": r.get("available"),
            "url": url,
        })

    out = pd.DataFrame(kept)
    print(f"Dropped {n_single_goodie} single/goodie/non-sealed, {n_notpoke} non-Pokemon.")
    print(f"Kept sealed Pokemon: {len(out)}")
    if out.empty:
        return out
    out = out.sort_values(["language", "series", "set", "kind", "shop"])
    out.to_excel(OUT, index=False)
    print(f"Wrote {OUT}")
    print("\nBy language:");  print(out.groupby("language").size().to_string())
    print("\nBy kind:");      print(out.groupby("kind").size().to_string())
    print(f"\nSet identified:    {(out['set'] != '').sum()}/{len(out)}")
    print(f"Series identified: {(out['series'] != '').sum()}/{len(out)}")
    return out


def load(df: pd.DataFrame):
    init_db()
    today = dt.date.today().isoformat()
    now = dt.datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        # Full re-categorize from raw each run: clear prior pokemon rows so counts
        # stay correct (cascades to their snapshots). Micromania is discovered by
        # its own browser-driven pipeline (scraper.discover_micromania), so it is
        # excluded here — otherwise this DELETE would wipe its rows every run.
        conn.execute("DELETE FROM products WHERE game='pokemon' AND platform != 'micromania'")
        cat = {(r["language"], r["set_code"], r["kind"]): r["id"] for r in conn.execute(
            "SELECT id, language, set_code, kind FROM catalog WHERE game='pokemon'")}
        ins = 0
        for _, r in df.iterrows():
            if not r["platform_pid"]:
                continue
            cid = cat.get((r["language"], r["set"], r["kind"]))
            cur = conn.execute("""
                INSERT INTO products (platform, shop, platform_pid, game, language,
                                      set_code, set_codes, series, kind, catalog_id,
                                      title, url, first_seen_at)
                VALUES (?, ?, ?, 'pokemon', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, shop, platform_pid) DO UPDATE SET
                    language=excluded.language, set_code=excluded.set_code,
                    set_codes=excluded.set_codes, series=excluded.series, kind=excluded.kind,
                    catalog_id=excluded.catalog_id, title=excluded.title, url=excluded.url
            """, (r["platform"], r["shop"], r["platform_pid"], r["language"],
                  r["set"], r["set_codes"], r["series"], r["kind"], cid,
                  r["title"], r["url"], today))
            pid = conn.execute(
                "SELECT id FROM products WHERE platform=? AND shop=? AND platform_pid=?",
                (r["platform"], r["shop"], r["platform_pid"])).fetchone()[0]
            avail = None if pd.isna(r["available"]) else int(r["available"])
            price = None if pd.isna(r["price_min"]) else float(r["price_min"])
            conn.execute("""
                INSERT INTO snapshots (product_id, observed_at, price_eur, available,
                                       raw_variant_count, stock_remaining)
                VALUES (?, ?, ?, ?, NULL, NULL)
            """, (pid, now, price, avail))
            ins += 1
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM products WHERE game='pokemon'").fetchone()[0]
    print(f"\nLoaded {ins} pokemon listings. Total pokemon products in DB: {n}")


def main():
    df = categorize()
    if df is not None and not df.empty:
        load(df)


if __name__ == "__main__":
    main()
