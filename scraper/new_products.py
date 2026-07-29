"""Detect untracked products across all tracked shops.

This sits on top of the scraper: it reuses each platform's existing
`discover_shop()` (no scraping/parsing logic is duplicated here) and only adds a
diff + review layer.

Two-step flow, driven by launch_new_products.bat:

  1. generate  -> re-discovers candidates on every shop, diffs them against the
                  `products` table AND the ignore list, and writes one row per
                  *new* candidate to data/new_products.xlsx with a blank
                  `decision` column.
  2. (you edit the file: put KEEP or DROP in `decision`, fill `set` for KEEPs,
      then save & close it)
  3. apply     -> KEEP rows are inserted into `products`; DROP rows are added to
                  data/ignored_products.json so they never come back next batch.

Identity key per product:  "<platform>|<shop>|<ident>"  where ident is the
platform product id, or "url:<path>" as a fallback when the shop gives no id.
The same ident is stored as products.platform_pid, so the diff stays consistent
across runs.
"""
import sys, io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import argparse
import datetime as dt
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from .db import connect, init_db
from .config import DATA_DIR
from . import cleanup
from . import (discover_shopify, discover_prestashop, discover_woocommerce, discover_wix,
               discover_powerboutique, discover_nextjs, discover_emonsite, discover_fantasysphere)

NEW_PRODUCTS_XLSX = DATA_DIR / "new_products.xlsx"
IGNORE_FILE = DATA_DIR / "ignored_products.json"

# (platform, list of shops, discover_shop fn, name of the pid field it returns)
PLATFORMS = [
    ("shopify",     discover_shopify.SHOPIFY_SHOPS,         discover_shopify.discover_shop,     "shopify_pid"),
    ("prestashop",  discover_prestashop.PRESTASHOP_SHOPS,   discover_prestashop.discover_shop,  "product_pid"),
    ("woocommerce", discover_woocommerce.WOOCOMMERCE_SHOPS, discover_woocommerce.discover_shop, "product_pid"),
    ("wix",         discover_wix.WIX_SHOPS,                 discover_wix.discover_shop,         "product_pid"),
    ("powerboutique", discover_powerboutique.POWERBOUTIQUE_SHOPS, discover_powerboutique.discover_shop, "product_pid"),
    ("nextjs",       discover_nextjs.NEXTJS_SHOPS,           discover_nextjs.discover_shop,       "product_pid"),
    ("emonsite",     discover_emonsite.EMONSITE_SHOPS,       discover_emonsite.discover_shop,     "product_pid"),
    ("fantasysphere", discover_fantasysphere.FANTASYSPHERE_SHOPS, discover_fantasysphere.discover_shop, "product_pid"),
]

COLUMNS = ["decision", "set", "game", "platform", "shop", "title",
           "price_min", "available", "product_pid", "url"]


# --------------------------------------------------------------------------- #
# Identity helpers
# --------------------------------------------------------------------------- #
def _norm_url(url: str) -> str:
    try:
        return urlparse(url).path.rstrip("/").lower()
    except Exception:
        return (url or "").lower()


def make_ident(pid, url: str) -> str:
    """Stable per-shop identifier: the platform id, or a url fallback.

    Normalizes the id so it survives an Excel round-trip: pandas reads an integer
    id (4321) back as a float (4321.0), which must collapse to the same key."""
    if pid is None or (isinstance(pid, float) and pid != pid):  # None / NaN
        pid = ""
    elif isinstance(pid, float) and pid.is_integer():
        pid = str(int(pid))
    else:
        pid = str(pid).strip()
        if pid.endswith(".0") and pid[:-2].isdigit():
            pid = pid[:-2]
    if pid and pid.lower() != "nan":
        return pid
    return "url:" + _norm_url(url)


def make_key(platform: str, shop: str, ident: str) -> str:
    return f"{platform}|{shop}|{ident}"


# --------------------------------------------------------------------------- #
# Ignore list
# --------------------------------------------------------------------------- #
def load_ignored() -> dict:
    """Return {key: {title, shop, dropped_at}}. Tolerates a missing/bad file."""
    if not IGNORE_FILE.exists():
        return {}
    try:
        data = json.loads(IGNORE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_ignored(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IGNORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Discovery + diff
# --------------------------------------------------------------------------- #
def gather_candidates() -> list[dict]:
    """Run discover_shop() for every shop on every platform (threaded).
    Returns a flat list of normalized candidate dicts (deduplicated by key)."""
    jobs = []  # (platform, shop, fn, pid_field)
    for platform, shops, fn, pid_field in PLATFORMS:
        for shop in shops:
            jobs.append((platform, shop, fn, pid_field))

    out, seen = [], set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fn, shop): (platform, shop, pid_field)
                for platform, shop, fn, pid_field in jobs}
        done = 0
        for fut in as_completed(futs):
            platform, shop, pid_field = futs[fut]
            done += 1
            try:
                rows = fut.result()
            except Exception as e:
                print(f"  [{done}/{len(jobs)}] {shop:<32} ERROR: {type(e).__name__}: {e}")
                continue
            print(f"  [{done}/{len(jobs)}] {shop:<32} {len(rows)} candidates")
            for r in rows:
                ident = make_ident(r.get(pid_field), r.get("url", ""))
                key = make_key(platform, shop, ident)
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "key": key,
                    "platform": platform,
                    "shop": shop,
                    "game": r.get("game", ""),
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "price_min": r.get("price_min"),
                    "available": r.get("available"),
                    "product_pid": r.get(pid_field) if r.get(pid_field) not in (None, "") else "",
                })
    return out


def load_tracked_keys() -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT platform, shop, platform_pid FROM products").fetchall()
    return {make_key(r["platform"], r["shop"], r["platform_pid"]) for r in rows}


def find_new(candidates: list[dict], tracked: set[str], ignored: dict) -> list[dict]:
    return [c for c in candidates if c["key"] not in tracked and c["key"] not in ignored]


# --------------------------------------------------------------------------- #
# generate  /  apply
# --------------------------------------------------------------------------- #
def generate() -> None:
    init_db()
    print("=== Discovering candidates on every shop ===")
    candidates = gather_candidates()
    tracked = load_tracked_keys()
    ignored = load_ignored()
    new = find_new(candidates, tracked, ignored)

    print("\n=== Summary ===")
    print(f"  candidates discovered : {len(candidates)}")
    print(f"  already tracked       : {len(tracked)}")
    print(f"  on ignore list        : {len(ignored)}")
    print(f"  NEW (untracked)       : {len(new)}")

    df = pd.DataFrame(new, columns=["platform", "shop", "game", "title",
                                    "price_min", "available", "product_pid", "url"])
    # add the two columns you fill in, and order them first
    df.insert(0, "set", "")
    df.insert(0, "decision", "")
    df = df[COLUMNS]
    if not df.empty:
        df = df.sort_values(["platform", "shop", "title"]).reset_index(drop=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        df.to_excel(NEW_PRODUCTS_XLSX, index=False)
    except PermissionError:
        print(f"\n/!\\ Could not write {NEW_PRODUCTS_XLSX} - is it open in Excel? Close it and retry.")
        sys.exit(1)

    print(f"\nWritten {len(df)} new candidate(s) to: {NEW_PRODUCTS_XLSX}")
    if len(df):
        print("Open it, put KEEP or DROP in the 'decision' column")
        print("(fill 'set' for the KEEP rows), then save & close.")


def apply() -> None:
    if not NEW_PRODUCTS_XLSX.exists():
        print(f"No file to apply ({NEW_PRODUCTS_XLSX} not found). Run 'generate' first.")
        return
    try:
        df = pd.read_excel(NEW_PRODUCTS_XLSX)
    except PermissionError:
        print(f"/!\\ Could not read {NEW_PRODUCTS_XLSX} - is it still open in Excel? Close it and retry.")
        sys.exit(1)

    if df.empty:
        print("Nothing to apply (file is empty).")
        return

    ignored = load_ignored()
    today = dt.date.today().isoformat()
    kept = dropped = 0
    skipped_blank = []        # no decision
    skipped_keep_no_set = []  # KEEP but no set code
    skipped_foreign = []      # KEEP but a non-French edition (OPTCG/Naruto)

    with connect() as conn:
        for _, r in df.iterrows():
            decision = str(r.get("decision", "") or "").strip().upper()
            platform = str(r.get("platform", "") or "").strip()
            shop = str(r.get("shop", "") or "").strip()
            url = str(r.get("url", "") or "").strip()
            title = str(r.get("title", "") or "").strip()
            game = str(r.get("game", "") or "").strip()
            pid_raw = r.get("product_pid")
            ident = make_ident(pid_raw, url)
            key = make_key(platform, shop, ident)

            if decision.startswith("K"):          # KEEP
                set_code = str(r.get("set", "") or "").strip()
                if not set_code or set_code.lower() == "nan":
                    skipped_keep_no_set.append((shop, title))
                    continue
                # Last-resort guard: OPTCG/Naruto are FR-only. Reject a KEEP that
                # is a non-French edition (e.g. a "VO"/"ENG"-tagged display that
                # slipped into the review sheet and got marked KEEP by mistake).
                if game in ("optcg", "naruto_mythos") and cleanup.is_foreign(title, url):
                    skipped_foreign.append((shop, title))
                    continue
                conn.execute("""
                    INSERT INTO products (platform, shop, platform_pid, game, set_code,
                                          title, url, first_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, shop, platform_pid) DO UPDATE SET
                        title = excluded.title, url = excluded.url,
                        set_code = excluded.set_code, game = excluded.game
                """, (platform, shop, ident, game, set_code, title, url, today))
                kept += 1
            elif decision.startswith("D"):        # DROP
                ignored[key] = {"title": title, "shop": shop, "dropped_at": today}
                dropped += 1
            else:
                skipped_blank.append((shop, title))
        conn.commit()

    save_ignored(ignored)

    print("=== Applied ===")
    print(f"  KEEP -> added/updated in DB : {kept}")
    print(f"  DROP -> added to ignore list: {dropped}")
    if skipped_keep_no_set:
        print(f"\n  /!\\ {len(skipped_keep_no_set)} KEEP row(s) had no 'set' code and were left pending:")
        for shop, title in skipped_keep_no_set[:20]:
            print(f"      [{shop}] {title[:60]}")
    if skipped_foreign:
        print(f"\n  /!\\ {len(skipped_foreign)} KEEP row(s) were non-French editions and were rejected:")
        for shop, title in skipped_foreign[:20]:
            print(f"      [{shop}] {title[:60]}")
    if skipped_blank:
        print(f"\n  {len(skipped_blank)} row(s) had no decision and will reappear next batch.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect and review untracked products.")
    ap.add_argument("command", choices=["generate", "apply"],
                    help="generate the review file, or apply your KEEP/DROP decisions")
    args = ap.parse_args()
    if args.command == "generate":
        generate()
    else:
        apply()


if __name__ == "__main__":
    main()
