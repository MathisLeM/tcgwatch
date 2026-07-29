"""Build a COMPLETE PokeCardex set reference (codes + FR names + logo URLs).

PokeCardex (https://www.pokecardex.com) lists far more sets than TCGdex — it is
our source of truth for the human-curated French set names and the set logos.
The site is a React SPA whose set data is *encrypted* (`__INITIAL_DATA_ALL_ENCRYPTED__`),
so we do NOT touch the SPA payload. Instead we use two stable, server-rendered
signals:

  * the list of international set codes lives in the sitemap
    (`/sitemap_fr.xml`, entries `<loc>.../series/<CODE></loc>`);
  * each set's French name is server-rendered in the SEO `og:title` of
    `/series/<CODE>` ("Série <Name> | PokéCardex").

Logos come from a confirmed CDN pattern (pokecardex.b-cdn.net):
  * localized FR international -> /assets/images/logos/<CODE>.png
  * US/EN international        -> /assets/images/logos/US/<CODE>.png
(JP/CHN logos use /logos_jp/ and /logos_chn/ keyed by the JP/ZH set_code; those
codes are not in sitemap_fr.xml, so they're handled downstream in
`fetch_pokecardex_images` against OUR reference, not here.)

robots.txt allows scraping (User-agent: * / Disallow: empty). We still pace with
PER_DOMAIN_DELAY and a real User-Agent. The build is resumable/idempotent: it
reloads the existing JSON and only fetches codes it doesn't already have (unless
--force).

Run:  python -m scraper.games.build_pokecardex [--limit N] [--force] [--dry-run]
"""
import argparse
import html
import json
import re
import time

import requests

from ..config import REFERENCE_DIR, USER_AGENT, REQUEST_TIMEOUT, PER_DOMAIN_DELAY
from ..timing import timed_main

BASE = "https://www.pokecardex.com"
SITEMAP_URL = f"{BASE}/sitemap_fr.xml"
CDN = "https://pokecardex.b-cdn.net"
OUT_FILE = REFERENCE_DIR / "pokecardex_sets.json"

HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xml"}

# Listing pages that look like a /series/<CODE> entry but are NOT sets.
_NON_SET_CODES = {"jp", "chn"}

# /series/<CODE> where <CODE> is the international abbreviation (CRI, PRE, SSP...).
_SERIES_LOC_RE = re.compile(
    r"<loc>\s*" + re.escape(BASE) + r"/series/([^<>/\s]+)\s*</loc>", re.IGNORECASE)
# og:title (and <title> as a fallback) — both carry "Série <Name> | PokéCardex".
_OG_TITLE_RE = re.compile(
    r'<meta\s+property="og:title"\s+content="([^"]*)"', re.IGNORECASE)
_TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^s[ée]rie\s+", re.IGNORECASE)   # "Série " / "Serie "
_SUFFIX = " | PokéCardex"


def _get(url, retries=3):
    """GET with timeout + backoff retry on 429 / 5xx / connection errors."""
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (i + 1))
                continue
            return None  # 4xx other than 429: not worth retrying
        except requests.RequestException:
            time.sleep(1 + i)
    return None


def fetch_codes() -> list[str]:
    """Return the international set codes from the FR sitemap (jp/chn excluded)."""
    r = _get(SITEMAP_URL)
    if not r:
        print(f"ERROR: could not fetch sitemap {SITEMAP_URL}")
        return []
    codes, seen = [], set()
    for m in _SERIES_LOC_RE.finditer(r.text):
        code = m.group(1).strip()
        if not code or code.lower() in _NON_SET_CODES:
            continue
        if code not in seen:           # de-dupe, preserve sitemap order
            seen.add(code)
            codes.append(code)
    return codes


def _clean_name(raw: str) -> str:
    """'Série Évolutions Prismatiques | PokéCardex' -> 'Évolutions Prismatiques'."""
    name = html.unescape(raw or "").strip()
    if name.endswith(_SUFFIX):
        name = name[: -len(_SUFFIX)]
    name = _PREFIX_RE.sub("", name).strip()
    return name


def fetch_name(code: str) -> str | None:
    """FR set name for a code via the server-rendered og:title (or <title>)."""
    r = _get(f"{BASE}/series/{code}")
    if not r:
        return None
    m = _OG_TITLE_RE.search(r.text) or _TITLE_RE.search(r.text)
    if not m:
        return None
    name = _clean_name(m.group(1))
    return name or None


def _entry(code: str, name_fr: str | None) -> dict:
    """One reference record. Logo URLs are pure pattern (no fetch needed here)."""
    return {
        "code": code,
        "name_fr": name_fr,
        "logo_url_fr": f"{CDN}/assets/images/logos/{code}.png",
        "logo_url_us": f"{CDN}/assets/images/logos/US/{code}.png",
        "url": f"{BASE}/series/{code}",
    }


def _load_existing() -> dict[str, dict]:
    if not OUT_FILE.exists():
        return {}
    try:
        data = json.loads(OUT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {row["code"]: row for row in data.get("sets", []) if row.get("code")}


def _write(existing: dict[str, dict], all_codes: list[str]) -> None:
    """Persist sorted by sitemap order, with any extra (stale) codes appended."""
    order = {c: i for i, c in enumerate(all_codes)}
    rows = sorted(existing.values(),
                  key=lambda r: order.get(r["code"], len(order)))
    out = {
        "source": BASE,
        "count": len(rows),
        "sets": rows,
    }
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def build(*, limit: int | None = None, force: bool = False,
          dry_run: bool = False) -> dict:
    """Fetch FR names for every sitemap code; build logo URLs. Returns counts."""
    print(f"=== Build PokeCardex reference ({'DRY-RUN' if dry_run else 'LIVE'}) ===")
    codes = fetch_codes()
    print(f"Sitemap set codes: {len(codes)}")
    if not codes:
        return {"fetched": 0, "skipped": 0, "no_name": 0, "errors": 0}

    existing = {} if force else _load_existing()
    if existing:
        print(f"Resuming: {len(existing)} codes already in {OUT_FILE.name}")

    fetched = skipped = no_name = errors = processed = 0
    for code in codes:
        if not force and code in existing and existing[code].get("name_fr"):
            skipped += 1
            continue
        if limit is not None and processed >= limit:
            break
        processed += 1

        if dry_run:
            print(f"  would fetch    {code}")
            fetched += 1
            continue

        name = fetch_name(code)
        if name is None:
            # Could be a transient error or a code with no SEO title. Keep an
            # entry (logos may still exist) but flag the missing name.
            errors += 1
            print(f"  WARN no-name   {code}  ({BASE}/series/{code})")
            existing[code] = _entry(code, None)
            no_name += 1
        else:
            fetched += 1
            existing[code] = _entry(code, name)
            print(f"  ok             {code:<10} {name}")
        # Persist incrementally so a long run stays resumable on interruption.
        _write(existing, codes)
        time.sleep(PER_DOMAIN_DELAY)  # be polite

    if dry_run:
        print("\n--- summary (dry-run) ---")
        print(f"  would fetch: {fetched}   already present: {skipped}")
    else:
        _write(existing, codes)
        print("\n--- summary ---")
        print(f"  fetched (named): {fetched}")
        print(f"  already present: {skipped}")
        print(f"  without name:    {no_name}")
        print(f"  errors:          {errors}")
        print(f"  total in file:   {len(existing)}  ->  {OUT_FILE}")
    return {"fetched": fetched, "skipped": skipped,
            "no_name": no_name, "errors": errors}


@timed_main
def main():
    ap = argparse.ArgumentParser(
        description="Build the PokeCardex set reference (codes + FR names + logos).")
    ap.add_argument("--limit", type=int, default=None,
                    help="Only fetch up to N new codes this run (for testing).")
    ap.add_argument("--force", action="store_true",
                    help="Refetch every code, ignoring the existing JSON.")
    ap.add_argument("--dry-run", action="store_true",
                    help="List what would be fetched without hitting set pages.")
    args = ap.parse_args()
    build(limit=args.limit, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
