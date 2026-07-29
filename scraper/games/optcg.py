"""OPTCG / Naruto Mythos game logic.

OPTCG and Naruto are tracked **French-only**, so `detect_language` returns 'fr'
for kept rows and None for foreign editions (which are dropped). Set-code and
kind logic is delegated to the existing `scraper.cleanup` module, which is the
canonical implementation curated during initial setup.
"""
from .. import cleanup
from .base import blob as _blob
from ..config import IMAGES_DIR

NAME = "optcg"
LANGUAGES = ["fr"]

# Canonical set names / ordering (French) — mirrors app.py.
SET_NAMES = {
    "OP09": "Les Nouveaux Empereurs", "OP10": "Sang Royal",
    "OP11": "Des Poings Vifs comme l'Éclair", "OP12": "L'Héritage du Maître",
    "OP13": "Successeurs", "OP14": "Les Sept de la Mer d'Azur",
    "OP15": "Aventure sur l'Île de Dieu", "OP16": "L'Heure de la Bataille",
    "OP17": "4th Anniversary",
    "EB02": "Anime 25th Collection", "EB03": "Heroines Edition",
    "PRB01": "The Best", "PRB02": "The Best Vol.2",
    "NRT-KS-ED1": "Konoha Shidō (ED.1)", "NRT-SS-ED1": "Shinobi Shiren Ch.2 (ED.1)",
}
SET_ORDER = ["OP09", "OP10", "OP11", "OP12", "OP13", "OP14", "OP15", "OP16", "OP17",
             "EB02", "EB03", "PRB01", "PRB02", "NRT-KS-ED1", "NRT-SS-ED1"]
VALID_SETS = cleanup.VALID_SETS

# Collection-handle / title keywords used by the discover_*.py modules.
COLLECTION_KEYWORDS = ["one-piece", "one piece", "onepiece", "optcg", "op-tcg",
                       "naruto", "mythos"]

KINDS = ["display", "booster", "case", "accessory"]

# Human-readable article-type labels for the block>set>type navigation (biggest
# first, like the Pokemon taxonomy).
KIND_ORDER = ["case", "display", "booster", "accessory"]
KIND_LABELS = {
    "case":      {"fr": "Carton (case)",               "en": "Case"},
    "display":   {"fr": "Display (boîte de boosters)",  "en": "Booster box (display)"},
    "booster":   {"fr": "Booster (à l'unité)",          "en": "Booster pack"},
    "accessory": {"fr": "Accessoire",                   "en": "Accessory"},
}


def kind_label(kind: str, language: str = "fr") -> str:
    lbl = KIND_LABELS.get(kind or "", {})
    return lbl.get(language) or lbl.get("en") or (kind or "?")


def set_name(set_code: str) -> str:
    """Localised (FR) set name, e.g. 'OP10' -> 'Sang Royal'."""
    return SET_NAMES.get(set_code, set_code)


def set_order_index(set_code: str) -> int:
    """Position in the canonical release order (unknown sets sort last)."""
    return SET_ORDER.index(set_code) if set_code in SET_ORDER else len(SET_ORDER)


# --------------------------------------------------------------------------- #
# Set / article-type images (files live at the images/ root, named
# "<SETCODE-without-dashes><suffix>.<ext>": BB = display box, SB = booster,
# SPC = case). The user curates these; a missing file just yields None.
# --------------------------------------------------------------------------- #
_KIND_SUFFIX = {"display": "BB", "booster": "SB", "case": "SPC"}
_IMG_EXTS = (".png", ".webp", ".jpg", ".jpeg")


def _find_image(code_nodash: str, suffix: str) -> str | None:
    for ext in _IMG_EXTS:
        p = IMAGES_DIR / f"{code_nodash}{suffix}{ext}"
        if p.exists():
            return str(p)
    return None


def set_image(set_code: str) -> str | None:
    """Representative image for a set (the display/booster-box art, else booster)."""
    base = (set_code or "").replace("-", "")
    return _find_image(base, "BB") or _find_image(base, "SB")


def kind_image(set_code: str, kind: str) -> str | None:
    """Image for a specific (set, article-type), or None if not curated."""
    base = (set_code or "").replace("-", "")
    suffix = _KIND_SUFFIX.get(kind)
    return _find_image(base, suffix) if suffix else None


def detect_language(title: str, url: str = "", extra: str = "") -> str | None:
    """OPTCG is FR-only: 'fr' for kept rows, None for foreign editions.

    `extra` carries the shop's category / breadcrumb names + short description,
    so JP/EN editions whose language only shows there (not in the title) are
    still recognised and dropped.
    """
    return None if cleanup.is_foreign(title or "", url or "", extra or "") else "fr"


def extract_set(title: str, url: str = "", game: str = "optcg") -> str:
    """Return a valid set code ('OP09'..'PRB02', 'NRT-*') or '' if none."""
    return cleanup._extract_set(_blob(title, url), game)


def classify_kind(title: str, price=None) -> str:
    """'case' | 'display' | 'booster' (delegates to cleanup.product_type)."""
    return cleanup.product_type(_blob(title).lower())
