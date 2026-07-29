"""Fill missing Pokemon set/series images from the TCGdex CDN.

Many Pokemon `sets` rows already carry a `logo_url` / `symbol_url` pointing at
the TCGdex CDN (assets.tcgdex.net). This script downloads those reference images
for sets that don't yet have a *curated* local image, so the dashboard always has
a visual even before someone hand-curates one.

This is reference data from TCGdex (not shop scraping), so the network call is
fine. We still pace requests with `PER_DOMAIN_DELAY` and set a real User-Agent.

Output goes to a dedicated `images/Pokemon/Image_Serie_auto/<set_code>.<ext>`
folder. Curated images in `Image_Serie` / `Image_block` are NEVER touched, and a
set already covered by a curated image (matched the same way the dashboard does,
via `pokemon.series_image`) is skipped.

Run:  python -m scraper.fetch_set_images [--limit N] [--dry-run]
"""
import argparse
import time

import requests

from .config import IMAGES_DIR, USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from .db import connect
from .games import pokemon
from .timing import timed_main

_OUT_DIR = IMAGES_DIR / "Pokemon" / "Image_Serie_auto"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "image/*"}


def _ext_from(url: str, content_type: str | None) -> str:
    """Pick a file extension from the URL, falling back to the content-type."""
    low = url.lower()
    for ext in (".png", ".webp", ".jpg", ".jpeg", ".gif"):
        if low.endswith(ext):
            return ext
    if content_type:
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
    return ".png"


def _already_local(set_code: str) -> bool:
    """True if a curated OR previously auto-fetched image already exists."""
    # Curated image (matched via the same logic the dashboard uses).
    if pokemon.series_image(set_code):
        return True
    # Auto folder may hold any extension for this set_code.
    if _OUT_DIR.exists():
        for f in _OUT_DIR.iterdir():
            if f.is_file() and f.stem == set_code:
                return True
    return False


def _missing_set_images():
    """Return [(set_code, name, image_url)] for FR/EN Pokemon sets that have a
    logo/symbol URL but no local image yet. Prefers logo_url over symbol_url.

    FR is preferred over EN when the same set_code appears in both, so the FR
    dashboard gets localised logos where available.
    """
    seen, out = set(), []
    with connect() as conn:
        # FR first, then EN, so FR wins per set_code; order by release date for
        # nicer/deterministic --limit batches.
        rows = conn.execute("""
            SELECT language, set_code, name, logo_url, symbol_url
            FROM sets
            WHERE game='pokemon'
              AND (logo_url IS NOT NULL OR symbol_url IS NOT NULL)
            ORDER BY CASE language WHEN 'fr' THEN 0 WHEN 'en' THEN 1 ELSE 2 END,
                     release_date
        """).fetchall()
    for r in rows:
        code = r["set_code"]
        if code in seen:
            continue
        seen.add(code)
        url = r["logo_url"] or r["symbol_url"]
        if url:
            out.append((code, r["name"], url))
    return out


def fetch_all(*, limit: int | None = None, dry_run: bool = False) -> dict:
    """Download missing set images. Returns counts."""
    candidates = _missing_set_images()
    print(f"=== Fetch Pokemon set images ({'DRY-RUN' if dry_run else 'LIVE'}) ===")
    print(f"Sets with a CDN URL: {len(candidates)}  ->  {_OUT_DIR}")

    downloaded = present = no_url = errors = processed = 0
    for set_code, name, url in candidates:
        if limit is not None and processed >= limit:
            break
        if not url:
            no_url += 1
            continue
        if _already_local(set_code):
            present += 1
            continue

        processed += 1
        if dry_run:
            print(f"  would fetch    {set_code:<10} <- {url}")
            downloaded += 1
            continue

        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200 or not resp.content:
                errors += 1
                print(f"  ERROR {resp.status_code:<4}   {set_code:<10} {url}")
                continue
            ext = _ext_from(url, resp.headers.get("Content-Type"))
            _OUT_DIR.mkdir(parents=True, exist_ok=True)
            dest = _OUT_DIR / f"{set_code}{ext}"
            dest.write_bytes(resp.content)
            downloaded += 1
            print(f"  downloaded     {set_code:<10} ({name or '?'})")
        except Exception as exc:  # noqa: BLE001 — log which set failed, keep going
            errors += 1
            print(f"  ERROR          {set_code:<10} {url}: {exc}")
        finally:
            time.sleep(PER_DOMAIN_DELAY)  # be polite to the CDN

    label = "would download" if dry_run else "downloaded"
    print("\n--- summary ---")
    print(f"  {label}: {downloaded}")
    print(f"  already present (curated or auto): {present}")
    if no_url:
        print(f"  without URL: {no_url}")
    if errors:
        print(f"  errors: {errors}")
    return {"downloaded": downloaded, "present": present,
            "no_url": no_url, "errors": errors}


@timed_main
def main():
    ap = argparse.ArgumentParser(
        description="Download missing Pokemon set images from the TCGdex CDN.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only fetch up to N missing images (for testing).")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be fetched without downloading.")
    args = ap.parse_args()
    fetch_all(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
