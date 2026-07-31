"""Character popularity — official One Piece "World Top 100" reader poll (2021).

Shueisha's worldwide popularity poll (WT100, held Jan–Feb 2021 for the 1000th
chapter) is the canonical reader-favourite ranking. Cards of beloved characters
(Luffy, Zoro, Hancock, Law…) command a price premium beyond rarity/play, so we
add the character's rank as a valuation feature.

We map a card's character name (from Limitless) to a poll rank by token overlap,
tolerating the punctuation/initial differences between the two sources
("Monkey.D.Luffy" ↔ "Monkey D. Luffy", "Trafalgar Law" ↔ "Trafalgar D. Water Law").

    from scraper.valuation.popularity import popularity_score, popularity_rank
    popularity_score("Monkey.D.Luffy")   # -> ~1.0 (rank 1)
    popularity_rank("Mamaragan")          # -> None (not in the top 100)

Source: One Piece WT100 global popularity poll, Shueisha (2021).
"""
from __future__ import annotations

import re

# Official WT100 result, positions 1..100 (index + 1 = rank).
WT100 = [
    "Monkey D. Luffy", "Roronoa Zoro", "Nami", "Vinsmoke Sanji", "Trafalgar D. Water Law",
    "Nico Robin", "Boa Hancock", "Carrot", "Portgas D. Ace", "Sabo",
    "Yamato", "Shanks", "Donquixote Rosinante", "Charlotte Katakuri", "Usopp",
    "Tony Tony Chopper", "Crocodile", "Jinbe", "Marco", "Donquixote Doflamingo",
    "Nefertari D. Vivi", "Bentham", "Eustass Kid", "Kouzuki Oden", "Perona",
    "Brook", "Smoker", "Franky", "Gol D. Roger", "Dracule Mihawk",
    "Edward Newgate", "Going Merry", "Silvers Rayleigh", "Buggy", "Enel",
    "Kuzan", "Woop Slap", "Tashigi", "Vinsmoke Reiju", "Bartolomeo",
    "X Drake", "Koby", "Rob Lucci", "Monkey D. Garp", "Charlotte Pudding",
    "Marshall D. Teach", "Kikunojo", "Izou", "Kouzuki Hiyori", "Shirahoshi",
    "Pell", "Issho", "Sakazuki", "Kurozumi Tama", "Killer",
    "Ulti", "Benn Beckman", "Koala", "Borsalino", "Gaimon",
    "Pedro", "Monkey D. Dragon", "Thousand Sunny", "Bepo", "Kaidou",
    "Rockstar", "Hiluluk", "Rebecca", "Paulie", "Urouge",
    "Namur", "Senor Pink", "Cavendish", "Gecko Moria", "Karoo",
    "Monet", "Kaku", "Orlumbus", "Emporio Ivankov", "Morgans",
    "Bell-mère", "Basil Hawkins", "Denjiro", "Gin", "Jewelry Bonney",
    "Charlotte Linlin", "Marguerite", "Wyper", "Kung-Fu Dugongs", "Charlotte Mont-d'Or",
    "Caesar Clown", "Kin'emon", "Zeff", "Vista", "Charlotte Perospero",
    "Kawamatsu", "Pandaman", "Bartholomew Kuma", "Charlotte Cracker", "Chouchou",
]

# Tokens that don't identify a character (initials, particles).
_STOP = {"d", "v", "the", "of", "von"}


def _tokens(name: str) -> set[str]:
    clean = re.sub(r"[^a-z0-9]+", " ", name.lower())
    return {t for t in clean.split() if len(t) > 1 and t not in _STOP}


_POLL = [(rank, _tokens(name)) for rank, name in enumerate(WT100, 1)]


def popularity_rank(card_name: str) -> int | None:
    """WT100 rank (1 = most popular) for a card's character, or None if unranked."""
    ct = _tokens(card_name or "")
    if not ct:
        return None
    best_rank: int | None = None
    best_overlap = 0
    for rank, pt in _POLL:
        if not pt:
            continue
        # One name's identifying tokens must be a subset of the other's (handles
        # truncated/extended names); pick the largest, most-popular such match.
        if pt <= ct or ct <= pt:
            overlap = len(pt & ct)
            if overlap > best_overlap or (overlap == best_overlap and
                                          (best_rank is None or rank < best_rank)):
                best_rank, best_overlap = rank, overlap
    return best_rank


def popularity_score(card_name: str) -> float:
    """0..1 popularity feature (rank 1 → ~1.0, rank 100 → ~0.01, unranked → 0)."""
    rank = popularity_rank(card_name)
    return 0.0 if rank is None else (len(WT100) - rank + 1) / len(WT100)
