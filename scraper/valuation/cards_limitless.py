"""Unified card source for the valuation model — Limitless, keyless.

One source gives everything the model needs, for *every* set (incl. the recent
OP13-16/EB03-04/PRB02 the GitHub mirror lacks) and with no API key:

  * rarity per card              — `/cards?q=set:<S> rarity:<R>` search
  * per-version EUR market price — `/cards/<code>` prints table (base vs alt "aa")
  * alt-art identity             — the "aa" / `?v=N` version rows

We skip Common/Uncommon entirely (not tracked). For each tracked base card we
keep every purchasable version with its EUR price; versions are classified into
the user's pull-rate tiers (see `odds.py`).

    from scraper.valuation.cards_limitless import build_cards, load_cards
    build_cards(["OP15"])           # scrape + consolidate (HTML cached on disk)
    cards = load_cards()            # {code: {...}}

CLI:
    python -m scraper.valuation.cards_limitless OP15 OP16 EB03   [--refresh]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

from . import VALUATION_DIR

BASE = "https://onepiece.limitlesstcg.com"
LIMITLESS_CACHE_DIR = VALUATION_DIR / "limitless"
OPTCG_CARDS_LL = VALUATION_DIR / "optcg_cards_limitless.json"
# Hand-curated corrections for versions Limitless mislabels (e.g. a SEC parallel
# tagged "manga"). Format: {"CODE": {"<v-number>": "aa|manga|fa|special|other"}}.
VERSION_OVERRIDES = VALUATION_DIR / "version_overrides.json"
_UA = {"User-Agent": "Mozilla/5.0 (TCGWatch/1.0 valuation research)"}

# Rarities we track (skip Common/Uncommon). Limitless short codes.
TRACKED_RARITIES = ("R", "SR", "SEC", "SP", "TR", "L")
RARITY_LABELS = {
    "Rare": "R", "Super Rare": "SR", "Secret Rare": "SEC", "Special": "SP",
    "Special Card": "SP", "Treasure Rare": "TR", "Leader": "L",
    "Promo": "P", "Common": "C", "Uncommon": "UC",
}


def _get(path: str, cache_name: str, *, refresh: bool = False, polite: float = 0.35) -> str:
    LIMITLESS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = LIMITLESS_CACHE_DIR / cache_name
    if cached.exists() and not refresh:
        return cached.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE + path, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    cached.write_text(text, encoding="utf-8")
    time.sleep(polite)
    return text


# ── pure parsers ─────────────────────────────────────────────────────────────
def parse_search_codes(html_text: str, set_code: str) -> list[str]:
    return sorted(set(re.findall(rf"/cards/({re.escape(set_code)}-\d{{3}})", html_text)))


_VARIANT_SUFFIXES = (("manga", "manga"), ("fa", "fa"), ("aa", "aa"))


def _version_kind(name: str, href: str, base_name: str) -> str:
    """Classify a print row *relative to the card's base booster print*.

    base    — the standard booster print (external/TCGplayer link)
    aa      — alt-art parallel   fa — full art   manga — manga rare
    special — same-name numbered variant (unlabelled SP / special art)
    other   — a DIFFERENT product (promo pack / collection / reprint): not a
              booster pull, excluded from the pull-rate model.
    """
    if "?v=" not in href:
        return "base"
    for suf, kind in _VARIANT_SUFFIXES:                 # "<base name> aa/fa/manga"
        if name.lower() == f"{base_name} {suf}".lower():
            return kind
    bn = base_name.strip().lower()
    if name.strip().lower() == bn or name.lower().startswith(bn + " "):
        return "special"       # same product, extra premium art (unnamed / wanted / …)
    return "other"                                      # cross-product reprint / promo


def parse_card_detail(html_text: str) -> dict:
    """{name, rarity, versions:[{name, kind, eur}]} from a /cards/<code> page."""
    tm = re.search(r"<title>\s*(.*?)\s*\(", html_text)
    card_name = html.unescape(tm.group(1)).strip() if tm else ""

    m = re.search(
        r"prints-current-details.*?text-lg.*?</span>\s*<span>\s*(.*?)\s*</span>",
        html_text, re.S)
    rarity_label = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    rarity = RARITY_LABELS.get(rarity_label, rarity_label.upper() or "?")

    tym = re.search(r'card-text-type.*?data-tooltip="Category">\s*(.*?)\s*</span>', html_text, re.S)
    card_type = re.sub(r"<[^>]+>", "", tym.group(1)).strip() if tym else ""

    rows: list[tuple[str, str, float | None]] = []
    j = html_text.find("card-prints-versions")
    if j != -1:
        block = html_text[j:html_text.find("</table>", j)]
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.S):
            tds = re.findall(r"<td.*?</td>", row, re.S)
            if not tds:
                continue
            name = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", tds[0])).strip())
            eur = re.search(r"([\d]+(?:[.,]\d+)?)\s*€", row)
            href = re.search(r'href=["\']?([^"\' >]+)', row)
            rows.append((name, href.group(1) if href else "",
                         float(eur.group(1).replace(",", ".")) if eur else None))

    base_name = next((n for n, h, _ in rows if "?v=" not in h), rows[0][0] if rows else "")

    def _vnum(href: str) -> int:
        m = re.search(r"\?v=(\d+)", href)
        return int(m.group(1)) if m else 0

    versions = [{"name": n, "kind": _version_kind(n, h, base_name), "v": _vnum(h), "eur": e}
                for n, h, e in rows]
    return {"name": card_name, "rarity": rarity, "type": card_type, "versions": versions}


# ── build ────────────────────────────────────────────────────────────────────
def enumerate_set(set_code: str, *, refresh: bool = False) -> dict[str, list[str]]:
    """{rarity: [codes]} for the tracked rarities of one set."""
    out: dict[str, list[str]] = {}
    for rar in TRACKED_RARITIES:
        q = urllib.parse.quote(f"set:{set_code} rarity:{rar}")
        htmltext = _get(f"/cards?q={q}", f"search_{set_code}_{rar}.html", refresh=refresh)
        codes = parse_search_codes(htmltext, set_code)
        if codes:
            out[rar] = codes
    return out


def build_cards(sets: list[str], *, refresh: bool = False) -> dict[str, dict]:
    """Scrape the given sets and consolidate into `code -> info` (rarity + prices)."""
    catalog: dict[str, dict] = {}
    for set_code in sets:
        by_rarity = enumerate_set(set_code, refresh=refresh)
        code_rarity = {c: rar for rar, codes in by_rarity.items() for c in codes}
        for code, search_rarity in sorted(code_rarity.items()):
            detail = _get(f"/cards/{code}", f"card_{code}.html", refresh=refresh)
            info = parse_card_detail(detail)
            base = next((v for v in info["versions"] if v["kind"] == "base"), None)
            catalog[code] = {
                "code": code,
                "set_code": set_code,
                "name": info["name"],
                "type": info["type"],
                "rarity": info["rarity"] or search_rarity,
                "base_eur": base["eur"] if base else None,
                "n_versions": len(info["versions"]),
                "kinds": sorted({v["kind"] for v in info["versions"]}),
                "versions": info["versions"],
            }
    VALUATION_DIR.mkdir(parents=True, exist_ok=True)
    OPTCG_CARDS_LL.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return catalog


def load_overrides() -> dict[str, dict[str, str]]:
    """Curated per-(code, version) kind corrections; {} if none."""
    if not VERSION_OVERRIDES.exists():
        return {}
    return json.loads(VERSION_OVERRIDES.read_text(encoding="utf-8"))


def load_cards() -> dict[str, dict]:
    if not OPTCG_CARDS_LL.exists():
        raise FileNotFoundError(
            f"{OPTCG_CARDS_LL} missing — run: python -m scraper.valuation.cards_limitless OP15 ...")
    cards = json.loads(OPTCG_CARDS_LL.read_text(encoding="utf-8"))
    ov = load_overrides()
    for code, per_v in ov.items():
        card = cards.get(code)
        if not card:
            continue
        for v in card.get("versions", []):
            fixed = per_v.get(str(v.get("v")))
            if fixed:
                v["kind"] = fixed
    return cards


def _main() -> None:
    ap = argparse.ArgumentParser(description="Build the Limitless card/rarity/price source.")
    ap.add_argument("sets", nargs="+", help="set codes, e.g. OP15 OP16 EB03")
    ap.add_argument("--refresh", action="store_true", help="ignore cached HTML")
    args = ap.parse_args()

    cat = build_cards([s.upper() for s in args.sets], refresh=args.refresh)
    by_rar: dict[str, int] = defaultdict(int)
    by_kind: dict[str, int] = defaultdict(int)
    for c in cat.values():
        by_rar[c["rarity"]] += 1
        for v in c["versions"]:
            if v["eur"] is not None:
                by_kind[v["kind"]] += 1
    print(f"Cards: {len(cat)} tracked -> {OPTCG_CARDS_LL}", file=sys.stderr)
    print("  by base rarity: " + ", ".join(f"{r}={n}" for r, n in sorted(by_rar.items())), file=sys.stderr)
    print("  priced versions: " + ", ".join(f"{k}={n}" for k, n in sorted(by_kind.items())), file=sys.stderr)


if __name__ == "__main__":
    _main()
