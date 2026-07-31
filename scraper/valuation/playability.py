"""Playability signal for OPTCG cards — Limitless metagame.

A card's *play demand* is how many competitive players need a copy. We read the
Limitless One Piece metagame:

  * `/decks` — ranked archetypes, each with a metagame **share** (%) and a leader.
  * `/decks/<id>/cards` — that archetype's average decklist: every card with
    `data-count` = mean copies across the archetype's lists (already blends copies
    × inclusion) and `data-id` = card code.

We aggregate share-weighted expected copies per card:

    exp_copies(card) = Σ_archetype  share_archetype × avg_copies_archetype(card)

i.e. the expected number of copies of that card in a *random* competitive deck.
A universal 4-of staple approaches 4; an archetype leader approaches its share;
a fringe card is near 0. `play_score` rescales this to 0..3 (relative to the most
-played card) for the valuation model.

    from scraper.valuation.playability import build_playability, load_playability
    build_playability()             # scrape + aggregate (raw HTML cached on disk)
    play = load_playability()       # {code: {...}}

CLI:
    python -m scraper.valuation.playability [--format OP16] [--refresh]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from collections import defaultdict

from . import VALUATION_DIR

BASE = "https://onepiece.limitlesstcg.com"
LIMITLESS_CACHE_DIR = VALUATION_DIR / "limitless"
PLAYABILITY = VALUATION_DIR / "playability.json"
_UA = {"User-Agent": "Mozilla/5.0 (TCGWatch/1.0 valuation research)"}

_DECK_ROW_RE = re.compile(
    r'<a class="deck-link" href="/decks/(\d+)">(.*?)</a>.*?<td>[\d,]+</td>\s*<td>([\d.]+)%</td>',
    re.S,
)
_LEADER_RE = re.compile(r'leader-icon[^>]*?/([A-Z]{2,4}\d{2}-\d{3})_[A-Z]{2}\.webp')
_CARD_RE = re.compile(r'<div class="decklist-card" data-count="([\d.]+)" data-id="([A-Z0-9-]+)"')
_TAG_RE = re.compile(r"<[^>]+>")


# ── pure parsers (unit-testable, no network) ─────────────────────────────────
def parse_metagame(html: str) -> list[dict]:
    """[{id, name, share(0..1), leader}] from a /decks metagame table."""
    out = []
    # Leaders sit in the row just before the deck-link; scan rows individually.
    for row in re.split(r"<tr>", html):
        m = _DECK_ROW_RE.search(row)
        if not m:
            continue
        lead = _LEADER_RE.search(row)
        out.append({
            "id": m.group(1),
            "name": _TAG_RE.sub(" ", m.group(2)).split(),  # tokens; joined below
            "share": float(m.group(3)) / 100.0,
            "leader": lead.group(1) if lead else None,
        })
    for d in out:
        d["name"] = " ".join(d["name"])
    return out


# A legal OPTCG deck holds at most 4 copies of a card; Limitless occasionally
# reports higher averages (DON!!/token artifacts), so clamp to the deck max.
DECK_MAX_COPIES = 4.0


def parse_archetype_cards(html: str) -> dict[str, float]:
    """{code: avg_copies} from a /decks/<id>/cards page (summed per code, capped)."""
    counts: dict[str, float] = defaultdict(float)
    for count, code in _CARD_RE.findall(html):
        counts[code.upper()] += float(count)
    return {code: min(c, DECK_MAX_COPIES) for code, c in counts.items()}


def aggregate(metagame: list[dict], cards_by_id: dict[str, dict[str, float]]) -> dict[str, dict]:
    """Share-weighted expected copies per card across the metagame."""
    exp: dict[str, float] = defaultdict(float)
    n_arch: dict[str, int] = defaultdict(int)
    best: dict[str, tuple[float, str, float]] = {}   # code -> (count, archetype, share)

    for arch in metagame:
        share = arch["share"]
        cards = dict(cards_by_id.get(arch["id"], {}))
        # Leaders may not appear in the decklist grid — inject 1 copy for the archetype.
        lead = arch.get("leader")
        if lead and lead not in cards:
            cards[lead] = 1.0
        for code, count in cards.items():
            exp[code] += share * count
            n_arch[code] += 1
            if code not in best or count > best[code][0]:
                best[code] = (count, arch["name"], share)

    max_exp = max(exp.values(), default=0.0) or 1.0
    catalog: dict[str, dict] = {}
    for code, e in exp.items():
        top_count, top_arch, top_share = best[code]
        catalog[code] = {
            "code": code,
            "exp_copies": round(e, 4),
            "play_score": round(3.0 * e / max_exp, 3),
            "n_archetypes": n_arch[code],
            "top_archetype": top_arch,
            "top_count": round(top_count, 2),
            "top_share": round(top_share, 4),
        }
    return catalog


# ── network + cache ──────────────────────────────────────────────────────────
def _get(path: str, cache_name: str, *, refresh: bool = False, polite: float = 0.4) -> str:
    LIMITLESS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = LIMITLESS_CACHE_DIR / cache_name
    if cached.exists() and not refresh:
        return cached.read_text(encoding="utf-8")
    req = urllib.request.Request(BASE + path, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    cached.write_text(html, encoding="utf-8")
    time.sleep(polite)
    return html


def build_playability(fmt: str | None = None, *, refresh: bool = False) -> dict[str, dict]:
    """Scrape the metagame + every archetype, aggregate, cache to playability.json."""
    q = f"?format={fmt}" if fmt else ""
    metagame = parse_metagame(_get(f"/decks{q}", f"metagame_{fmt or 'current'}.html", refresh=refresh))

    cards_by_id: dict[str, dict[str, float]] = {}
    for arch in metagame:
        html = _get(f"/decks/{arch['id']}/cards", f"deck_{arch['id']}.html", refresh=refresh)
        cards_by_id[arch["id"]] = parse_archetype_cards(html)

    catalog = aggregate(metagame, cards_by_id)
    VALUATION_DIR.mkdir(parents=True, exist_ok=True)
    PLAYABILITY.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return catalog


def load_playability() -> dict[str, dict]:
    if not PLAYABILITY.exists():
        return build_playability()
    return json.loads(PLAYABILITY.read_text(encoding="utf-8"))


def _main() -> None:
    ap = argparse.ArgumentParser(description="Build the OPTCG playability signal (Limitless meta).")
    ap.add_argument("--format", default=None, help="metagame format, e.g. OP16 (default: current)")
    ap.add_argument("--refresh", action="store_true", help="re-download (ignore cached HTML)")
    args = ap.parse_args()

    cat = build_playability(fmt=args.format, refresh=args.refresh)
    top = sorted(cat.values(), key=lambda c: -c["exp_copies"])[:15]
    print(f"Playability: {len(cat)} cards -> {PLAYABILITY}")
    print(f"{'code':10} {'exp_cp':>7} {'play':>5}  top archetype")
    for c in top:
        print(f"{c['code']:10} {c['exp_copies']:7.2f} {c['play_score']:5.2f}  "
              f"{c['top_archetype']} ({c['top_count']}x)")


if __name__ == "__main__":
    _main()
