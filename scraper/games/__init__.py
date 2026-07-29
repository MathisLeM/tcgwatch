"""Per-game logic registry.

Each game (optcg, pokemon) provides its own set table, language detector,
set-code extractor and product-kind classifier. The platform fetch/discover
infrastructure is game-agnostic and dispatches here via `get_game(name)`.
"""
from . import optcg, pokemon

GAMES = {
    "optcg": optcg,
    "pokemon": pokemon,
}


def get_game(name: str):
    try:
        return GAMES[name]
    except KeyError:
        raise ValueError(f"Unknown game: {name!r}. Known: {list(GAMES)}")
