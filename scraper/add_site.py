"""Add a new website to the tracker.

Interactive flow:
  1. Ask URL, name, optional OPTCG/Naruto deep links.
  2. Probe the URL -> detect platform (shopify / prestashop / woocommerce / other).
  3. If 'other', exit gracefully.
  4. Run discovery for just this one shop.
  5. Apply the standard cleanup pipeline (cleanup.apply_cleanup).
  6. Write a review Excel; pause for user to prune.
  7. Append remaining rows to data/discovered_<platform>.xlsx.
  8. Register the shop in extra_shops.json (so future discovery includes it).
  9. Reload the DB from curated Excel files.
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from .config import USER_AGENT, REQUEST_TIMEOUT, DATA_DIR
from .cleanup import apply_cleanup
from .shop_registry import add_shop
from . import (discover_shopify, discover_prestashop, discover_woocommerce, discover_wix,
               discover_powerboutique, discover_nextjs, discover_emonsite, discover_fantasysphere)
from . import load_curated

HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}


def prompt(label, default=""):
    val = input(f"  {label}").strip()
    return val or default


def detect_platform(url: str) -> tuple[str, str]:
    """Return ('shopify'|'prestashop'|'woocommerce'|'other', detail)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    except Exception as e:
        return "other", f"fetch failed: {type(e).__name__}"
    if r.status_code != 200:
        return "other", f"HTTP {r.status_code}"
    body = r.text.lower()
    # Probe definitive endpoints
    host = urlparse(r.url).netloc or urlparse(url).netloc
    # Shopify
    try:
        rp = requests.get(f"https://{host}/products.json?limit=1", headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if rp.status_code == 200 and "products" in rp.json():
            return "shopify", host
    except Exception: pass
    # WooCommerce Store API
    try:
        rw = requests.get(f"https://{host}/wp-json/wc/store/products?per_page=1", headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if rw.status_code == 200 and isinstance(rw.json(), list):
            return "woocommerce", host
    except Exception: pass
    # Wix Stores: the storefront serves a Wix Stores access token
    try:
        rx = requests.get(f"https://{host}{discover_wix.TOKENS_PATH}", headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if rx.status_code == 200 and (rx.json().get("apps") or {}).get(discover_wix.STORES_APP_ID):
            return "wix", host
    except Exception: pass
    # PrestaShop signatures
    if re.search(r"var\s+prestashop\s*=|id=[\"']prestashop[\"']|/modules/ps_", r.text, re.IGNORECASE):
        return "prestashop", host
    # Powerboutique: /dhtml/ endpoints + .product_box tiles with idproduit
    if "/dhtml/" in r.text and ("product_box" in r.text or "idproduit" in r.text):
        return "powerboutique", host
    # e-monsite: identified by its X-EMS-Server response header
    if r.headers.get("X-EMS-Server") or "e-monsite" in body:
        return "emonsite", host
    # Next.js shops we have a bespoke strategy for (PlayIn / Parkage)
    if host in discover_nextjs.NEXTJS_SHOPS:
        return "nextjs", host
    # Bespoke custom storefronts we have a per-shop strategy for
    if host in discover_fantasysphere.FANTASYSPHERE_SHOPS:
        return "fantasysphere", host
    # Heuristic other-platform detection (just for the user-facing message)
    if "shopify" in body and "cdn.shopify.com" in body: return "shopify", host
    if "wp-content" in body or "woocommerce" in body: return "woocommerce", host
    if "wix.com" in body or "x-wix" in body: return "other", "Wix (no Stores app detected)"
    if "__NEXT_DATA__" in body or "/_next/static" in body:
        return "other", "Next.js (needs a bespoke per-shop strategy in discover_nextjs.py)"
    if "magento" in body: return "other", "Magento"
    return "other", "unrecognized"


def run_discovery(platform: str, host: str) -> list:
    """Run single-shop discovery and return raw rows (before cleanup)."""
    if platform == "shopify":
        return discover_shopify.discover_shop(host)
    if platform == "prestashop":
        return discover_prestashop.discover_shop(host)
    if platform == "woocommerce":
        return discover_woocommerce.discover_shop(host)
    if platform == "wix":
        return discover_wix.discover_shop(host)
    if platform == "powerboutique":
        return discover_powerboutique.discover_shop(host)
    if platform == "nextjs":
        return discover_nextjs.discover_shop(host)
    if platform == "emonsite":
        return discover_emonsite.discover_shop(host)
    if platform == "fantasysphere":
        return discover_fantasysphere.discover_shop(host)
    raise ValueError(platform)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Homepage URL of the new shop")
    ap.add_argument("--name", help="Shop name (purely for display)")
    ap.add_argument("--optcg-url", help="Direct OPTCG category URL (PrestaShop hint)")
    ap.add_argument("--naruto-url", help="Direct Naruto Mythos category URL (PrestaShop hint)")
    args = ap.parse_args()

    print("\n" + "=" * 62)
    print("  Add a new website to the OPTCG / Naruto tracker")
    print("=" * 62 + "\n")

    url = args.url or prompt("Website URL: ")
    if not url:
        print("No URL given. Aborting."); sys.exit(1)
    if not url.startswith("http"):
        url = "https://" + url
    name = args.name or prompt("Shop name (optional, press Enter to skip): ")
    optcg_url = args.optcg_url or prompt("Direct OPTCG category URL (optional): ")
    naruto_url = args.naruto_url or prompt("Direct Naruto category URL (optional): ")

    host = urlparse(url).netloc

    print(f"\n[1/6] Probing {host} ...")
    platform, detail = detect_platform(url)
    if platform == "other":
        print(f"  Detected: {detail}.")
        print(f"  This site uses a platform we don't auto-scrape (Shopify/PrestaShop/WooCommerce only).")
        print(f"  Aborting. You can still track it via the dashboard later if you build a custom scraper.")
        sys.exit(1)
    print(f"  Platform: {platform.upper()}  ({detail})")

    # Build optional direct_urls for PS shops
    direct_urls_for_registry = None
    if platform == "prestashop" and (optcg_url or naruto_url):
        entries = []
        if optcg_url:  entries.append({"game": "optcg",        "url": optcg_url,  "scope": "dedicated"})
        if naruto_url: entries.append({"game": "naruto_mythos","url": naruto_url, "scope": "dedicated"})
        direct_urls_for_registry = entries

    print(f"\n[2/6] Registering {host} in shop_registry (extra_shops.json) ...")
    if add_shop(platform, host, direct_urls=direct_urls_for_registry):
        print(f"  Added.")
    else:
        print(f"  Already registered (continuing — will re-discover).")

    print(f"\n[3/6] Running discovery for {host} ...")
    # Reload modules so they pick up the new shop_registry entries
    import importlib
    for m in (discover_shopify, discover_prestashop, discover_woocommerce, discover_wix,
              discover_powerboutique, discover_nextjs, discover_emonsite, discover_fantasysphere):
        importlib.reload(m)
    raw_rows = run_discovery(platform, host)
    print(f"  Raw rows from discovery: {len(raw_rows)}")
    if not raw_rows:
        print("  Discovery found 0 booster/display products. The shop may not carry OPTCG/Naruto.")
        print("  Aborting before cleanup.")
        sys.exit(0)

    # Normalize raw rows -> the columns the main Excel files use
    df_raw = pd.DataFrame(raw_rows)
    # Ensure key columns exist
    for c in ("game","shop","title","url","price_min","available","product_pid"):
        if c not in df_raw.columns: df_raw[c] = None
    df_raw["price_max"] = df_raw.get("price_max", df_raw["price_min"])
    if "shopify_pid" in df_raw.columns and "product_pid" not in df_raw.columns:
        df_raw["product_pid"] = df_raw["shopify_pid"]

    print(f"\n[4/6] Applying cleanup pipeline (keyword filters + set codes) ...")
    df_clean = apply_cleanup(df_raw)
    print(f"  After cleanup: {len(df_clean)} rows")
    if df_clean.empty:
        print("  Nothing left after cleanup. Aborting.")
        sys.exit(0)

    review_path = DATA_DIR / f"review_{re.sub(r'[^a-z0-9]+','_',host.lower())}.xlsx"
    df_clean.to_excel(review_path, index=False)
    print(f"\n[5/6] Wrote review file: {review_path}")
    print("\n  >>> Open the file, REMOVE any rows you don't want tracked, save it.")
    print("  >>> The 'set' column is already filled. Keep the 'product_pid' values intact.")
    input("\n  Press ENTER when done... ")

    df_kept = pd.read_excel(review_path)
    print(f"  You kept {len(df_kept)} rows.")
    if df_kept.empty:
        print("  Nothing to merge. Aborting.")
        sys.exit(0)

    # Merge into the platform's main file
    main_path = DATA_DIR / f"discovered_{platform}.xlsx"
    if main_path.exists():
        main_df = pd.read_excel(main_path)
    else:
        main_df = pd.DataFrame(columns=df_kept.columns)
    # Avoid duplicates by (shop, product_pid)
    if "product_pid" in main_df.columns and "product_pid" in df_kept.columns:
        existing = set(zip(main_df["shop"].astype(str), main_df["product_pid"].astype(str)))
        before = len(df_kept)
        df_kept = df_kept[~df_kept.apply(
            lambda r: (str(r["shop"]), str(r["product_pid"])) in existing, axis=1)]
        dropped_dups = before - len(df_kept)
        if dropped_dups:
            print(f"  Skipped {dropped_dups} duplicate rows already in {main_path.name}.")
    if df_kept.empty:
        print("  All rows were duplicates. Nothing new to add.")
    else:
        merged = pd.concat([main_df, df_kept], ignore_index=True)
        merged.to_excel(main_path, index=False)
        print(f"  Merged into {main_path.name}: {len(merged)} total rows ({len(df_kept)} new).")

    print(f"\n[6/6] Reloading DB from curated Excel files ...")
    load_curated.main()

    print("\n" + "=" * 62)
    print(f"  Done! {host} is now part of regular scraping.")
    print(f"  Run launch_scraping.bat to take a fresh snapshot.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
