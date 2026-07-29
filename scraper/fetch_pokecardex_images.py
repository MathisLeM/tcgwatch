"""Download PokeCardex set logos, mapped onto OUR set_codes.

PokeCardex hosts high-quality set logos on a CDN (pokecardex.b-cdn.net). This
script downloads them into a dedicated `images/Pokemon/Image_Serie_pokecardex/`
folder, named by OUR set_code so the dashboard can resolve them by code.

Mapping from our reference (`data/reference/pokemon_sets.json`):
  * international (fr/en): the set's `abbreviation` (CRI, PRE, SSP...) is exactly
    the PokeCardex international code ->
        FR  /assets/images/logos/<ABBR>.png      (preferred, localized)
        US  /assets/images/logos/US/<ABBR>.png   (fallback)
  * Japanese (ja):  our set_code (SV9, S12a...) -> /assets/images/logos_jp/<code>.png
  * Chinese  (zh):  our set_code              -> /assets/images/logos_chn/<code>.png

Curated images in `Image_Serie` / `Image_block` and the TCGdex auto-fetch in
`Image_Serie_auto` are NEVER touched. This is reference data from a CDN (not shop
scraping); network is fine but we pace with PER_DOMAIN_DELAY and a real
User-Agent, and the run is idempotent (skips set_codes already downloaded here
unless --force).

Run:  python -m scraper.fetch_pokecardex_images [--limit N] [--force] [--dry-run]
"""
import argparse
import time

import requests

from .config import IMAGES_DIR, USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from .games import pokemon
from .timing import timed_main

CDN = "https://pokecardex.b-cdn.net"
_OUT_DIR = IMAGES_DIR / "Pokemon" / "Image_Serie_pokecardex"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "image/*"}

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _candidate_urls(row: dict) -> list[str]:
    """Ordered PokeCardex logo URL candidates for one of our set rows.

    International prefers the FR (localized) logo, then the US/EN one; JA/ZH use
    their own logo folders keyed by our set_code. Returns [] when we have no
    mapping handle (e.g. an international set without an abbreviation)."""
    lang, code = row.get("language"), row.get("set_code")
    if not code:
        return []
    if lang in ("fr", "en"):
        abbr = row.get("abbreviation")
        if not abbr:
            return []
        return [f"{CDN}/assets/images/logos/{abbr}.png",
                f"{CDN}/assets/images/logos/US/{abbr}.png"]
    if lang == "ja":
        return [f"{CDN}/assets/images/logos_jp/{code}.png"]
    if lang == "zh":
        return [f"{CDN}/assets/images/logos_chn/{code}.png"]
    return []  # ko: PokeCardex has no Korean logos


def _targets() -> list[tuple[str, str, str | None, list[str]]]:
    """Return [(set_code, language, name, [urls])], one per set_code.

    FR is preferred over EN when a set_code exists in both (FR logos are
    localized). Built from the in-repo reference JSON via `pokemon._load_reference`
    so it needs no DB access."""
    by_lang = pokemon._load_reference()["by_lang"]
    out, seen = [], set()
    # Order languages so FR wins for shared international codes, then EN, then CJK.
    for lang in ("fr", "en", "ja", "zh", "ko"):
        for code, row in sorted(by_lang.get(lang, {}).items()):
            if code in seen:
                continue
            urls = _candidate_urls(row)
            if not urls:
                continue
            seen.add(code)
            out.append((code, lang, row.get("name"), urls))
    return out


def _already_curated(set_code: str) -> bool:
    """True if a hand-curated image (in `Image_Serie`, matched by name) already
    exists for this set_code — we must never shadow curated art. Checks only the
    curated folder, NOT our own pokecardex output (which `series_image` also
    resolves), so already-downloaded logos report as 'present', not 'curated'."""
    ref = pokemon._load_reference()["by_lang"]
    name = ((ref.get("fr", {}).get(set_code) or {}).get("name")
            or (ref.get("en", {}).get(set_code) or {}).get("name"))
    return bool(name and pokemon._serie_images().get(pokemon._img_slug(name)))


def _already_downloaded(set_code: str) -> bool:
    return (_OUT_DIR / f"{set_code}.png").exists()


def _fetch_png(urls: list[str]) -> bytes | None:
    """Try each URL; return the first body that is a real PNG, else None."""
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.content[:8] == _PNG_MAGIC:
            return r.content
    return None


def fetch_all(*, limit: int | None = None, force: bool = False,
              dry_run: bool = False) -> dict:
    """Download PokeCardex logos for our sets. Returns counts."""
    print(f"=== Fetch PokeCardex set logos ({'DRY-RUN' if dry_run else 'LIVE'}) ===")
    targets = _targets()
    print(f"Mappable set_codes: {len(targets)}  ->  {_OUT_DIR}")

    downloaded = curated = present = no_logo = errors = processed = 0
    for set_code, lang, name, urls in targets:
        # Don't shadow a curated image; don't redo work unless --force.
        if _already_curated(set_code):
            curated += 1
            continue
        if not force and _already_downloaded(set_code):
            present += 1
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1

        if dry_run:
            print(f"  would fetch    {set_code:<10} [{lang}] {urls[0]}")
            downloaded += 1
            continue

        content = _fetch_png(urls)
        try:
            if content is None:
                no_logo += 1
                print(f"  no logo        {set_code:<10} [{lang}] ({name or '?'})")
                continue
            _OUT_DIR.mkdir(parents=True, exist_ok=True)
            (_OUT_DIR / f"{set_code}.png").write_bytes(content)
            downloaded += 1
            print(f"  downloaded     {set_code:<10} [{lang}] ({name or '?'})")
        except OSError as exc:  # log which set failed, keep going
            errors += 1
            print(f"  ERROR          {set_code:<10} {exc}")
        finally:
            time.sleep(PER_DOMAIN_DELAY)  # be polite to the CDN

    label = "would download" if dry_run else "downloaded"
    print("\n--- summary ---")
    print(f"  {label}:                 {downloaded}")
    print(f"  skipped (curated image): {curated}")
    print(f"  skipped (already here):  {present}")
    print(f"  no logo on CDN:          {no_logo}")
    if errors:
        print(f"  errors:                  {errors}")
    return {"downloaded": downloaded, "curated": curated, "present": present,
            "no_logo": no_logo, "errors": errors}


@timed_main
def main():
    ap = argparse.ArgumentParser(
        description="Download PokeCardex set logos mapped onto our set_codes.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only fetch up to N logos this run (for testing).")
    ap.add_argument("--force", action="store_true",
                    help="Re-download even if the logo is already present.")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be fetched without downloading.")
    args = ap.parse_args()
    fetch_all(limit=args.limit, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
