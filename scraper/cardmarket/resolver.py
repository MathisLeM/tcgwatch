"""Resolve a Cardmarket One Piece single-card URL to a Cardmarket idProduct,
using only the local catalogue JSON (no scraping — Cardmarket 403s bots).

Ported from OPTCG_Tracker/singles_resolver.py; reads the catalogues from
`data/cardmarket/` (products_singles_*.json + products_nonsingles_*.json).
"""
from __future__ import annotations

import glob
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import CM_DIR

CODE_IN_NAME = re.compile(r"\(([A-Z0-9]+-[0-9]+[A-Za-z0-9\-]*)\)")
CODE_IN_SLUG = re.compile(r"([A-Z]{1,4}[0-9]{0,3}-[0-9]{2,4})")
SET_NAME_STOPWORDS = {
    "booster", "box", "boxes", "sleeved", "pack", "packs", "case",
    "the", "of", "a", "edition", "collection", "deck", "starter",
    "non", "english", "op", "eb", "prb",
}


def _newest(pattern: str) -> Path | None:
    files = sorted(glob.glob(str(CM_DIR / pattern)))
    return Path(files[-1]) if files else None


def _load_catalogue(pattern: str) -> list[dict]:
    path = _newest(pattern)
    if path is None or not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("products", [])


def _tokens(text: str) -> set[str]:
    raw = re.split(r"[^a-z0-9]+", text.lower())
    return {t for t in raw if t and t not in SET_NAME_STOPWORDS}


@dataclass
class Candidate:
    idProduct: int
    name: str
    idExpansion: int
    set_name: str
    is_non_english: bool
    score: float = 0.0


@dataclass
class Resolution:
    url: str
    code: str | None
    expansion_slug: str | None
    best: Candidate | None
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.best is not None


class SingleResolver:
    def __init__(self) -> None:
        singles = _load_catalogue("products_singles_*.json")
        nonsingles = _load_catalogue("products_nonsingles_*.json")

        self.exp_name: dict[int, str] = {}
        for p in nonsingles:
            e = p["idExpansion"]
            name = p["name"]
            cur = self.exp_name.get(e)
            if cur is None or ("(Non-English)" in cur and "(Non-English)" not in name):
                self.exp_name[e] = name

        self.by_code: dict[str, list[dict]] = {}
        for p in singles:
            m = CODE_IN_NAME.search(p["name"])
            if m:
                self.by_code.setdefault(m.group(1).upper(), []).append(p)

    @staticmethod
    def parse_url(url: str) -> tuple[str | None, str | None]:
        parts = [seg for seg in urlparse(url).path.split("/") if seg]
        expansion_slug = card_slug = None
        if "Singles" in parts:
            i = parts.index("Singles")
            if i + 1 < len(parts):
                expansion_slug = unquote(parts[i + 1])
            if i + 2 < len(parts):
                card_slug = unquote(parts[i + 2])
        card_slug = card_slug or (parts[-1] if parts else "")
        code = None
        matches = CODE_IN_SLUG.findall(card_slug or "")
        if matches:
            code = matches[-1].upper()
        return code, expansion_slug

    def resolve(self, url: str) -> Resolution:
        code, expansion_slug = self.parse_url(url)
        res = Resolution(url=url, code=code, expansion_slug=expansion_slug, best=None)
        if not code:
            return res
        entries = self.by_code.get(code, [])
        slug_tokens = _tokens(expansion_slug or "")
        for p in entries:
            set_name = self.exp_name.get(p["idExpansion"], "")
            cand = Candidate(
                idProduct=p["idProduct"], name=p["name"], idExpansion=p["idExpansion"],
                set_name=set_name, is_non_english="(Non-English)" in set_name,
            )
            overlap = slug_tokens & _tokens(set_name)
            cand.score = len(overlap)
            if slug_tokens and overlap == slug_tokens:
                cand.score += 0.5
            if cand.is_non_english:
                cand.score -= 0.25
            res.candidates.append(cand)
        res.candidates.sort(key=lambda c: (-c.score, c.idProduct))
        if res.candidates:
            res.best = res.candidates[0]
        return res
