"""Effective article-type (`kind`) resolution.

OPTCG / Naruto Mythos products are stored **without** a `kind` (the column is
NULL for them), but their type is deterministic from the title. Rather than
backfilling the DB (which would need a prod migration), we derive the kind
on-read for these games. Pokemon keeps its stored kind (classified at scrape
time from multilingual titles/descriptions, not reproducible from the title
alone), so it is never recomputed here.
"""
from __future__ import annotations

from typing import Optional

# Games whose kind is derived from the title on-read (French-only, few products).
DERIVED_KIND_GAMES = frozenset({"optcg", "naruto_mythos"})


def effective_kind(game: str, stored_kind: Optional[str], title: str) -> Optional[str]:
    """Return the kind to use: the stored one if present, else derived for
    OPTCG/Naruto from the title, else the stored value (Pokemon)."""
    if stored_kind:
        return stored_kind
    if game in DERIVED_KIND_GAMES:
        from scraper.games import optcg
        return optcg.classify_kind(title or "")
    return stored_kind


def kind_label(game: str, kind: str, language: str = "fr") -> str:
    """Human-readable article type ("display" -> "Display", "etb" -> "Coffret
    Élite"). Same labels the catalogue shows, so the two views agree; falls back
    to the raw slug for anything not curated."""
    if game in DERIVED_KIND_GAMES:
        from scraper.games import optcg
        return optcg.kind_label(kind, language) or kind
    from scraper.games import pokemon
    return pokemon.kind_label(kind, language) or kind
