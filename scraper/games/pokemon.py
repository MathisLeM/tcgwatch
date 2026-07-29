"""Pokemon TCG game logic.

Tracked **multi-language**: FR / EN / JA / KO / ZH. Unlike OPTCG, language is a
kept dimension, not a drop filter — `detect_language` returns the language code.

Set reference data is built from TCGdex by `scraper.games.build_pokemon_sets`
and cached in `data/reference/pokemon_sets.json` (SWSH-era -> present).
"""
import html
import json
import re
import unicodedata
from functools import lru_cache
from .base import blob as _blob, slug_last
from ..config import REFERENCE_DIR

NAME = "pokemon"
LANGUAGES = ["fr", "en", "ja", "ko", "zh"]
KINDS = ["case", "display", "etb", "upc", "bundle", "tripack", "duopack", "blister",
         "coffret", "minitin", "booster", "accessory"]

# Human-readable article-type labels (used by the block > set > type navigation),
# ordered biggest → smallest so a set's article types read top-down like the
# containment precedence in `_kind_from`.
KIND_ORDER = ["case", "display", "etb", "upc", "coffret", "bundle", "tripack",
              "duopack", "blister", "minitin", "booster", "accessory", "unknown"]
KIND_LABELS = {
    "case":      {"fr": "Carton (case)",                 "en": "Case"},
    "display":   {"fr": "Display (boîte de boosters)",   "en": "Booster box (display)"},
    "etb":       {"fr": "Coffret Dresseur d'Élite (ETB)", "en": "Elite Trainer Box (ETB)"},
    "upc":       {"fr": "Ultra Premium Collection (UPC)", "en": "Ultra Premium Collection (UPC)"},
    "coffret":   {"fr": "Coffret / Tin",                 "en": "Box / Tin"},
    "bundle":    {"fr": "Bundle (lot de boosters)",      "en": "Bundle"},
    "tripack":   {"fr": "Tripack (3 boosters)",          "en": "Tripack (3 packs)"},
    "duopack":   {"fr": "Duopack (2 boosters)",          "en": "Duopack (2 packs)"},
    "blister":   {"fr": "Blister",                       "en": "Blister"},
    "minitin":   {"fr": "Mini Tin / Pokébox",           "en": "Mini Tin"},
    "booster":   {"fr": "Booster (à l'unité)",           "en": "Booster pack"},
    "accessory": {"fr": "Accessoire",                    "en": "Accessory"},
    "unknown":   {"fr": "Autre / non classé",           "en": "Other / unclassified"},
}


def kind_label(kind: str, language: str = "fr") -> str:
    """Readable article-type label for a kind code, e.g. 'display' -> 'Display …'."""
    lbl = KIND_LABELS.get(kind or "unknown", KIND_LABELS["unknown"])
    return lbl.get(language) or lbl.get("en") or (kind or "unknown")

# ----------------------------------------------------------------------------- #
# Set reference (loaded from the TCGdex-built JSON)
# ----------------------------------------------------------------------------- #
_REF_FILE = REFERENCE_DIR / "pokemon_sets.json"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


# Typographic punctuation that shops use interchangeably with the ASCII forms.
# Folding it lets a single keyword ("pin's", "duo-pack") match every variant.
_PUNCT_FOLD = str.maketrans({
    "’": "'", "‘": "'", "ʼ": "'",            # curly / modifier apostrophes
    "–": "-", "—": "-", "−": "-",            # en/em dash, minus
    " ": " ", " ": " ",                           # non-breaking spaces
})


def _norm(s: str) -> str:
    """Lowercase, accent-stripped, whitespace-collapsed search text.

    HTML entities (`&rsquo;`, `&#8211;`, `&amp;` ...) are decoded and typographic
    apostrophes/dashes folded to ASCII first, so a keyword like "pin's" matches
    "Pin’s" and "Pin&rsquo;s" alike — shop titles mix all of these freely."""
    s = html.unescape(s or "").translate(_PUNCT_FOLD)
    return re.sub(r"\s+", " ", _strip_accents(s.lower())).strip()


_SERIES_FILE = REFERENCE_DIR / "pokemon_series.json"


@lru_cache(maxsize=1)
def _load_reference() -> dict:
    """Return reference indexes: per-language set rows, name->code lists, and
    code->series_id."""
    if not _REF_FILE.exists():
        return {"sets": [], "by_lang": {}, "names": {}, "code_series": {}}
    data = json.loads(_REF_FILE.read_text(encoding="utf-8"))
    by_lang, names, code_series, code_abbr, abbr_index = {}, {}, {}, {}, {}
    for row in data.get("sets", []):
        lang, code = row["language"], row["set_code"]
        by_lang.setdefault(lang, {})[code] = row
        if row.get("series"):
            code_series.setdefault(code, row["series"])
        if row.get("abbreviation"):
            code_abbr.setdefault(code, row["abbreviation"])
            abbr_index.setdefault(row["abbreviation"].upper(), code)
        if row.get("name"):
            names.setdefault(lang, []).append((_norm(row["name"]), code))
    # Longest names first so "Écarlate et Violet 151" wins over "Écarlate et Violet".
    for lang in names:
        names[lang].sort(key=lambda t: len(t[0]), reverse=True)
    return {"sets": data.get("sets", []), "by_lang": by_lang, "names": names,
            "code_series": code_series, "code_abbr": code_abbr, "abbr_index": abbr_index}


# ----------------------------------------------------------------------------- #
# Naming convention: Block (ME/EV/EB) > Set abbreviation (CRI/OBF/PRE) > name
# ----------------------------------------------------------------------------- #
BLOCK_CODES = {"me": "ME", "sv": "EV", "swsh": "EB", "sm": "SL", "xy": "XY",
               "bw": "NB", "mc": "MCD", "tcgp": "PKT"}

# Japanese TCGdex series ids are uppercase era codes (SV / S / M / SM / XY ...)
# that map onto the same international blocks the FR/EN dictionaries use. Without
# this, JA/KO/ZH rows surface a raw id ("SV", "S") instead of a real block name.
# S = Sword & Shield era (2020-2024) -> swsh; SV = Scarlet & Violet -> sv;
# M = Mega Evolution (2025+) -> me; SM = Sun & Moon -> sm; XY -> xy.
_JP_SERIES_TO_BLOCK = {"sv": "sv", "s": "swsh", "m": "me", "sm": "sm", "xy": "xy"}


def normalize_series(series_id: str) -> str:
    """Map a (possibly Japanese, uppercase) series id onto the canonical block id.

    Returns the international block id when known ('SV'->'sv', 'S'->'swsh'), else
    the id unchanged. Lets series name/code/image lookups work for JA/KO/ZH rows.
    """
    if not series_id:
        return ""
    return _JP_SERIES_TO_BLOCK.get(series_id.lower(), series_id)


def block_code(series_id: str) -> str:
    if not series_id:
        return ""
    sid = normalize_series(series_id)
    return BLOCK_CODES.get(sid, sid.upper())


def abbreviation_of(set_code: str) -> str:
    return _load_reference()["code_abbr"].get(set_code, "")


# Curated display order for the block navigation: newest / most-relevant era first.
# Any block not listed sorts after these (by its most recent set's release date).
BLOCK_DISPLAY_ORDER = ["me", "sv", "tcgp", "swsh", "sm", "xy", "mc"]


def canonical_block(series_id: str) -> str:
    """Unified block id merging the JP era ids onto the international blocks
    ('S'->'swsh', 'SV'->'sv', 'M'->'me', 'SM'->'sm'); '' stays ''."""
    return normalize_series(series_id) if series_id else ""


def set_block(set_code: str) -> str:
    """Canonical block id for a set_code (via its reference series), or ''."""
    return canonical_block(series_of_code(set_code))


def block_sort_key(block_id: str, latest_release: str = "") -> tuple:
    """Sort key placing curated blocks in `BLOCK_DISPLAY_ORDER` first (in that
    order), then any other block by most-recent release date, newest first."""
    b = canonical_block(block_id)
    if b in BLOCK_DISPLAY_ORDER:
        return (0, BLOCK_DISPLAY_ORDER.index(b), "")
    # Unlisted blocks: after curated ones, newest set first.
    return (1, 0, _invert_date(latest_release))


def _invert_date(d: str) -> str:
    """Return a string that sorts inversely to an ISO date (newest first)."""
    if not d:
        return "~"          # empty dates last
    return "".join(chr(255 - ord(c)) if c.isdigit() else c for c in d)


@lru_cache(maxsize=1)
def _load_series() -> dict:
    """{'names': {lang: {id: name}}, 'detect': [(norm_name, series_id)]}."""
    names = {}
    if _SERIES_FILE.exists():
        names = json.loads(_SERIES_FILE.read_text(encoding="utf-8"))
    detect = []
    for lang, mp in names.items():
        for sid, nm in mp.items():
            detect.append((_norm(nm), sid))
    # Hardcoded aliases for the modern blocks (shops vary on & / et / and).
    for nm, sid in [("ecarlate et violet", "sv"), ("scarlet and violet", "sv"),
                    ("scarlet violet", "sv"), ("epee et bouclier", "swsh"),
                    ("sword and shield", "swsh"), ("sword shield", "swsh"),
                    ("mega evolution", "me"), ("mega-evolution", "me"),
                    ("soleil et lune", "sm"), ("sun and moon", "sm")]:
        detect.append((nm, sid))
    detect.sort(key=lambda t: len(t[0]), reverse=True)
    return {"names": names, "detect": detect}


def series_of_code(set_code: str) -> str:
    return _load_reference()["code_series"].get(set_code, "")


def series_name(series_id: str, language: str = "fr") -> str:
    names = _load_series()["names"]
    sid = normalize_series(series_id)
    # Try the raw id first (covers JA-only series with their own dict entry), then
    # the normalized block id in the requested language, then EN, then the id.
    return (names.get(language, {}).get(series_id)
            or names.get(language, {}).get(sid)
            or names.get("en", {}).get(sid)
            or names.get("en", {}).get(series_id)
            or sid)


# ----------------------------------------------------------------------------- #
# Block / series visuals (images), resolved by normalized French name
# ----------------------------------------------------------------------------- #
from ..config import IMAGES_DIR

_BLOCK_IMG_DIR = IMAGES_DIR / "Pokemon" / "Image_block"
_SERIE_IMG_DIR = IMAGES_DIR / "Pokemon" / "Image_Serie"
# Auto-downloaded set logos, keyed by set_code (filename = "<set_code>.<ext>"):
#   Image_Serie_pokecardex -> PokeCardex CDN  (fetch_pokecardex_images.py)
#   Image_Serie_auto       -> TCGdex CDN      (fetch_set_images.py)
_PKCDX_IMG_DIR = IMAGES_DIR / "Pokemon" / "Image_Serie_pokecardex"
_AUTO_IMG_DIR = IMAGES_DIR / "Pokemon" / "Image_Serie_auto"
_IMG_PREFIXES = ("bloc-", "bloc_", "serie_", "serie-", "série_", "série-")
_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _img_slug(s: str) -> str:
    """Normalize a name/filename to a comparable slug (accents off, separators -> space)."""
    s = _strip_accents((s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _index_images(folder) -> dict:
    """{normalized-slug: relative-path-str} for every image in `folder`.
    Filename prefixes ('bloc-', 'serie_') are stripped before slugifying."""
    out = {}
    if not folder.exists():
        return out
    for f in folder.iterdir():
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        stem = f.stem
        low = stem.lower()
        for p in _IMG_PREFIXES:
            if low.startswith(p):
                stem = stem[len(p):]
                break
        out[_img_slug(stem)] = str(f)
    return out


@lru_cache(maxsize=1)
def _block_images() -> dict:
    return _index_images(_BLOCK_IMG_DIR)


@lru_cache(maxsize=1)
def _serie_images() -> dict:
    return _index_images(_SERIE_IMG_DIR)


def _index_by_code(folder) -> dict:
    """{set_code: absolute-path-str} for auto folders whose files are named by
    set_code (e.g. 'sv03.5.png', 'me01.png'). First extension found wins."""
    out = {}
    if not folder.exists():
        return out
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in _IMG_EXTS and f.stem not in out:
            out[f.stem] = str(f)
    return out


@lru_cache(maxsize=1)
def _pokecardex_images() -> dict:
    return _index_by_code(_PKCDX_IMG_DIR)


@lru_cache(maxsize=1)
def _auto_images() -> dict:
    return _index_by_code(_AUTO_IMG_DIR)


def block_image(series_id: str) -> str | None:
    """Absolute path to a block image, or None.

    Priority: curated block image (matched on the block's French name) > the logo
    of a representative (most recent) set in that block, so blocks without a hand-
    curated banner (Sun & Moon, McDonald's, TCG Pocket) still get a visual."""
    if not series_id:
        return None
    curated = _block_images().get(_img_slug(series_name(normalize_series(series_id), "fr")))
    if curated:
        return curated
    # Fallback: newest set in the block that has any image.
    for code in reversed(sets_in_block(series_id)):
        img = series_image(code)
        if img:
            return img
    return None


def sets_in_block(series_id: str) -> list:
    """Ordered (by release) list of set_codes whose block is `series_id`.
    De-duplicated across languages (a code shared by FR/EN appears once)."""
    block = canonical_block(series_id)
    rows = _load_reference()["sets"]
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: x.get("release_date") or ""):
        code = r["set_code"]
        if code in seen:
            continue
        if canonical_block(r.get("series")) == block:
            seen.add(code)
            out.append(code)
    return out


def series_image(set_code: str) -> str | None:
    """Absolute path to a set/series image, or None.

    Priority: curated (`Image_Serie`, matched on the set's FR/EN name) >
    PokeCardex auto (`Image_Serie_pokecardex/<set_code>.png`) >
    TCGdex auto (`Image_Serie_auto/<set_code>.<ext>`). The two auto folders are
    keyed by set_code (not name), so they cover sets whose name we don't index.
    """
    if not set_code:
        return None
    ref = _load_reference()["by_lang"]
    name = ((ref.get("fr", {}).get(set_code) or {}).get("name")
            or (ref.get("en", {}).get(set_code) or {}).get("name"))
    if name:
        curated = _serie_images().get(_img_slug(name))
        if curated:
            return curated
    return _pokecardex_images().get(set_code) or _auto_images().get(set_code)


def set_names(language: str) -> dict:
    """{set_code: localised name} for a language, sorted by release date."""
    rows = _load_reference()["by_lang"].get(language, {})
    return {c: r.get("name", c) for c, r in
            sorted(rows.items(), key=lambda kv: kv[1].get("release_date") or "")}


def set_order(language: str) -> list:
    rows = _load_reference()["by_lang"].get(language, {})
    return [c for c, _ in sorted(rows.items(), key=lambda kv: kv[1].get("release_date") or "")]


def valid_sets(language: str | None = None) -> set:
    ref = _load_reference()
    if language:
        return set(ref["by_lang"].get(language, {}))
    return {r["set_code"] for r in ref["sets"]}


# ----------------------------------------------------------------------------- #
# Language detection (FR / EN / JA / KO / ZH)
# ----------------------------------------------------------------------------- #
_LANG_WORDS = {
    "ja": ["japonais", "japanese", "japon", "jpn", "import jap", "version jap"],
    "ko": ["coreen", "coréen", "korean", "korea", "kor "],
    "zh": ["chinois", "chinese", "taiwan", "version chinoise"],
    "en": ["anglais", "english", "version anglaise", "us version"],
    "fr": ["francais", "français", "french", "version francaise", "version française"],
}
# Explicit UPPERCASE language tags on the *raw* title (e.g. "... - EN -", "(JP)").
# Case-sensitive so the French stopword "en" is never mistaken for English.
_UPPER_MARK = re.compile(r"\b(FR|EN|US|JP|JA|JPN|KR|KO|KOR|CN|ZH|TW|CHN)\b")
_MARK_MAP = {"FR": "fr", "EN": "en", "US": "en", "JP": "ja", "JA": "ja",
             "JPN": "ja", "KR": "ko", "KO": "ko", "KOR": "ko",
             "CN": "zh", "ZH": "zh", "TW": "zh", "CHN": "zh"}
_LANG_SUFFIX = re.compile(r"-(en|fr|jp|ja|ko|kr|cn|zh|tw)$")
_SUFFIX_MAP = {"jp": "ja", "kr": "ko", "tw": "zh", "cn": "zh",
               "ja": "ja", "ko": "ko", "zh": "zh", "en": "en", "fr": "fr"}


def _script_lang(text: str) -> str | None:
    has_kana = has_hangul = has_cjk = False
    for ch in text:
        o = ord(ch)
        if 0x3040 <= o <= 0x30FF:          # hiragana / katakana
            has_kana = True
        elif 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
            has_hangul = True
        elif 0x4E00 <= o <= 0x9FFF:        # CJK ideographs (kanji / hanzi)
            has_cjk = True
    if has_kana:
        return "ja"
    if has_hangul:
        return "ko"
    if has_cjk:
        return "zh"          # ideographs without kana/hangul -> Chinese
    return None


def detect_language(title: str, url: str = "", extra: str = "", default: str = "fr") -> str:
    """Return one of fr/en/ja/ko/zh.

    ~99% of the tracked shops are French, so language defaults to FR unless there
    is a *strong* signal: CJK script, an explicit language word (anglais/japonais
    /...), an UPPERCASE language tag (EN/JP/KR... — case-sensitive so the French
    word "en" never reads as English), or a URL slug suffix (-en/-jp/...).
    """
    raw = f"{title or ''} {extra or ''} {url or ''}"
    by_script = _script_lang(raw)
    if by_script:
        return by_script
    text = _norm(raw)
    for lang, words in _LANG_WORDS.items():
        if any(w in text for w in words):
            return lang
    m = _UPPER_MARK.search(f"{title or ''} {extra or ''}")
    if m:
        return _MARK_MAP[m.group(1)]
    m = _LANG_SUFFIX.search(slug_last(url))
    if m:
        return _SUFFIX_MAP[m.group(1)]
    return default


# ----------------------------------------------------------------------------- #
# Set extraction
# ----------------------------------------------------------------------------- #
# International TCGdex code (sv03, swsh10, me04, sv03.5 ...).
_CODE_RE = re.compile(r"\b(sv|swsh|me)\s?0?\d{1,2}(?:\.\d)?\b", re.IGNORECASE)
# French community codes: EB## (Épée et Bouclier = swsh##), EV## (Écarlate et
# Violet = sv##), optionally with a half-set decimal (EV3.5 = sv03.5). 1:1 for the
# main numbered sets; always validated against the reference.
_FR_CODE_RE = re.compile(r"\b(eb|ev)\s?-?\s?0?(\d{1,2})(\.\d)?\b", re.IGNORECASE)
_FR_CODE_SERIES = {"eb": "swsh", "ev": "sv"}

# Japanese TCGdex set codes carry letter prefixes/suffixes the international regex
# can't express: SV9, SV5M, SV9a, S12, S12a, CS2b, M2, SVK, SVLN ... We match a
# generic JP-looking token then *validate* it against the JA reference (which is
# the source of truth), so we never invent a code. Case-insensitive on both sides.
_JP_CODE_RE = re.compile(r"\b(sv|cs|sm|s|m)\s?-?\s?(\d{1,2}(?:\.\d)?[a-z]?|[a-z]{1,3})\b",
                         re.IGNORECASE)


def _fr_code_to_set(blob: str) -> str:
    m = _FR_CODE_RE.search(blob)
    if not m:
        return ""
    half = m.group(3) or ""
    series = _FR_CODE_SERIES[m.group(1).lower()]
    # Sets use a zero-padded two-digit number (sv03, sv03.5, swsh10); build both
    # the padded and un-padded forms and keep whichever the reference knows.
    num = int(m.group(2))
    for code in (f"{series}{num:02d}{half}", f"{series}{num}{half}"):
        if code in valid_sets():
            return code
    return ""


@lru_cache(maxsize=8)
def _jp_code_index(language: str) -> dict:
    """{lowercased set_code: canonical set_code} for a CJK language, for fast
    case-insensitive validation of Japanese-style codes found in titles."""
    return {c.lower(): c for c in valid_sets(language)}


def _jp_code_to_set(raw: str, language: str = "ja") -> str:
    """Match a Japanese-style set code (SV9 / SV5M / S12a / CS2b / M2 ...) in `raw`.

    Validates against the *listing's own language* reference so set identity stays
    `(language, set_code)` (KO/ZH have their own SV/S numbering). Returns the
    canonical set_code, or '' if no JP-looking token is a real set in that
    language. Takes the *longest* valid match so 'SV9a' wins over 'SV9'.
    """
    idx = _jp_code_index(language if language in ("ja", "ko", "zh") else "ja")
    best = ""
    for m in _JP_CODE_RE.finditer(raw):
        token = (m.group(1) + m.group(2)).lower().replace(" ", "").replace("-", "")
        canon = idx.get(token)
        if canon and len(canon) > len(best):
            best = canon
    return best


_ABBR_RE = re.compile(r"\b[A-Z]{2,4}\b")
# Lot / multi-set markers (a single product bundling several sets).
_LOT_KW = ["lot de", "lot des", "assortiment", "multipack", "multi pack",
           "mini tins", "mini-tins", "ensemble de", "set de plusieurs", "lot pokemon"]


def _abbr_to_set(raw: str) -> str:
    """Match an official set abbreviation (OBF/PRE/CRI...) as an UPPERCASE token."""
    ab = _load_reference()["abbr_index"]
    for m in _ABBR_RE.finditer(raw):
        code = ab.get(m.group(0))
        if code:
            return code
    return ""


# The "151" set is a special case: its name is a bare number, so a generic block
# name ("Écarlate et Violet" -> sv01) would otherwise win the longest-name match.
# A standalone "151" token is an unambiguous, high-confidence signal.
_151_RE = re.compile(r"(?<!\d)151(?!\d)")
# JA/KO/ZH all number "151" as SV2a; FR/EN use sv03.5.
_151_BY_LANG = {"ja": "SV2a", "ko": "SV2a", "zh": "SV2a"}
_151_DEFAULT = "sv03.5"


def _is_151(blob_n: str, language: str) -> str:
    """Return the 151 set_code for the language if a bare '151' token is present."""
    if not _151_RE.search(blob_n):
        return ""
    code = _151_BY_LANG.get(language, _151_DEFAULT)
    return code if code in valid_sets(language if language in _151_BY_LANG else None) else ""


def extract_set(title: str, url: str = "", language: str = "fr", extra: str = "") -> str:
    """Primary set_code, or '' if not identified. First of extract_sets()."""
    s = extract_sets(title, url, language, extra, multi=False)
    return s[0] if s else ""


def _is_lot(blob_n: str) -> bool:
    return any(k in blob_n for k in _LOT_KW)


def extract_sets(title: str, url: str = "", language: str = "fr", extra: str = "",
                 multi: bool = True) -> list:
    """Return the set codes a product belongs to.

    Order of signals: explicit TCGdex code -> French EB##/EV## code -> official
    abbreviation (OBF/PRE/...) -> localized set-name match (preferred language
    first, then any). When the product is a *lot* (and multi=True) ALL distinct
    sets named in the text are returned (so a "Lot ... Astres Radieux + Origine
    Perdue" is findable under both EB10 and EB11); otherwise just the primary.
    """
    blob = f"{_blob(title, url)} {extra or ''}"
    blob_n = _norm(blob)
    raw = f"{title or ''} {extra or ''}"
    ref = _load_reference()

    primary = ""
    m = _CODE_RE.search(blob)
    if m and m.group(0).lower().replace(" ", "") in valid_sets():
        primary = m.group(0).lower().replace(" ", "")
    # Japanese codes (SV9 / SV5M / S12a / M2 ...) — used for JA/KO/ZH listings,
    # where these tokens are the canonical identifier (KR/ZH imports reuse the JP
    # numbering). Always validated against the JA reference, so never invented.
    if not primary and language in ("ja", "ko", "zh"):
        primary = _jp_code_to_set(raw, language)
    # A bare "151" is an unambiguous set signal and must beat the block name match
    # ("Écarlate et Violet : 151" -> sv03.5, not sv01).
    if not primary:
        primary = _is_151(blob_n, language)
    if not primary:
        primary = _fr_code_to_set(blob_n) or _abbr_to_set(raw)

    # All localized set-name matches, longest-first, non-overlapping (single text).
    langs = [language] + [l for l in LANGUAGES if l != language]
    spans = []
    for lang in langs:
        for norm_name, code in ref["names"].get(lang, []):
            if len(norm_name) >= 4:
                idx = blob_n.find(norm_name)
                if idx >= 0:
                    spans.append((idx, idx + len(norm_name), code))
            else:
                mm = re.search(rf"(?<!\d){re.escape(norm_name)}(?!\d)", blob_n)
                if mm:
                    spans.append((mm.start(), mm.end(), code))
    spans.sort(key=lambda t: t[1] - t[0], reverse=True)
    occupied, name_codes = [], []
    for s, e, code in spans:
        if any(not (e <= os or s >= oe) for os, oe in occupied):
            continue
        occupied.append((s, e))
        name_codes.append((s, code))
    name_codes.sort()
    ordered = [c for _, c in name_codes]

    if not primary:
        primary = ordered[0] if ordered else ""
    if not primary:
        return []
    if not (multi and _is_lot(blob_n)):
        return [primary]
    # Lot: primary + every other distinct set named, in order of appearance.
    out = [primary]
    for c in ordered:
        if c not in out:
            out.append(c)
    return out


def extract_series(title: str, url: str = "", language: str = "fr", extra: str = "",
                   set_code: str = "") -> str:
    """Return the block/series id (e.g. 'me', 'sv', 'swsh'), or ''.

    Prefers the series of an already-identified set; otherwise flags the series
    name (Méga-Évolution / Écarlate et Violet / ...) in the text.
    """
    if set_code:
        s = series_of_code(set_code)
        if s:
            return s
    blob_n = _norm(f"{_blob(title, url)} {extra or ''}")
    for norm_name, sid in _load_series()["detect"]:
        if len(norm_name) >= 4 and norm_name in blob_n:
            return sid
    return ""


# ----------------------------------------------------------------------------- #
# Product-kind classification (Pokemon sealed taxonomy)
# ----------------------------------------------------------------------------- #
SEALED_KINDS = {"case", "display", "etb", "upc", "bundle", "tripack", "duopack",
                "blister", "coffret", "minitin", "booster"}

# Goodies / accessories / singles — drop these even if other words match.
_GOODIE_KW = [
    "sleeve", "protege carte", "protege-carte", "protege cartes", "pochette",
    "classeur", "binder", "portfolio", "porte folio", "porte-folio", "album",
    "cahier range", "toploader", "top loader", "playmat", "tapis de jeu",
    "tapis de jeux", "deck box", "deckbox", "deck case", "deck holder",
    "porte carte", "porte-carte", "porte cartes", "boite de rangement",
    "boîte de rangement", "rangement", "porte cle", "porte-cle", "porte-clé",
    "porte cles", "peluche", "plush", "figurine", "funko", "pin s", "pin's",
    "pins deluxe", "pin s deluxe", "pin box", "badge", "mug", "tasse", "gourde",
    "t shirt", "t-shirt", "poster", "affiche", "stylo", "carnet", "veilleuse",
    "lampe", "puzzle", "dé ", "dés ", "dice", "jeton", "coin (", "sticker",
    "autocollant", "serviette", "casquette", "porte-monnaie",
    # Empty display/ETB boxes sold as collector storage (no cards inside).
    "boite vide", "boîte vide", "boite metal vide", "presentoir vide",
    # Plexiglass / hard-case protectors sold FOR a sealed product (not the product
    # itself): "Protection en plexiglass pour display / ETB / bundle / booster".
    "plexiglass", "plexi glass", "protection plexi", "protege display",
    "protege-display", "boitier de protection", "boite de protection",
    "case de protection", "capsule de protection", "hard case",
]
# Pre-constructed / theme / battle decks: playable decks, not sealed-set product.
# Matched as multi-word phrases so a bare "deck" inside "deck box" stays handled
# by the goodie/accessory rules and a real "Deck Holder" isn't double-counted.
_DECK_KW = [
    "deck de combat", "deck combat", "battle deck", "deck a theme",
    "deck a themes", "theme deck", "deck preconstruit", "deck pre construit",
    "deck build box", "deck build", "deck blister", "deck avec booster",
    "starter vmax", "starter deck", "battle academy", "academie de combat",
    "v battle deck", "bundle deck", "deck bundle",
]
_SINGLE_KW = [
    "carte a l unite", "à l'unité", "a l unite", "single card", "carte single",
    "psa ", "psa10", "psa 10", "graded", "gradee", "ccc ", "pca ",
    "reverse holo", "holo rare", "carte gradee", "carte certifiee",
]
# "carte promo" / "promo card" is ambiguous: a sealed display can advertise an
# included promo ("Display ... avec carte promo"), while a loose promo single is
# just "Carte Promo Pikachu". So it only counts as a single when NO sealed-kind
# word is present (see `is_sealed`). Listed separately from `_SINGLE_KW`.
_PROMO_SINGLE_KW = ["carte promo", "promo card"]
# CJK single-card / loose-item markers (normalized with _norm so they match the
# NFKD-decomposed text). Guards the JA/KO bare-'box' relaxation against loose
# singles ("単品" = single item, "낱장" = loose card).
_CJK_SINGLE_KW = [_norm(k) for k in ("単品", "シングル", "낱장", "단품", "单卡", "單卡")]
# Banned products: not set-attached sealed product (Trainer's Toolkit, etc.).
_BANLIST = [
    "necessaire du dresseur", "trainer toolkit", "trainer s toolkit",
    "trainers toolkit", "trainer's toolkit", "trainer tool kit",
]
# Other trading-card games that leak into a shop's "Pokemon" collection page
# (cross-listed accessories, mixed category menus). A listing naming one of these
# is not a Pokemon product, so `is_sealed` rejects it. Kept as distinctive multi-
# word / unambiguous tokens so a Pokemon title is never dropped by accident
# (e.g. "magic the gathering"/"mtg" not bare "magic"; "dragon ball" not "dragon").
_OTHER_TCG_KW = [
    "lorcana", "yu-gi-oh", "yu gi oh", "yugioh", "weiss schwarz", "weiss",
    "shadowverse", "hololive", "uma musume", "digimon", "dragon ball",
    "cardfight", "vanguard", "flesh and blood", "gundam card", "altered tcg",
    "grand archive", "union arena", "riftbound", "star wars unlimited",
    "metazoo", "sorcery contested", "wixoss", "buddyfight", "force of will",
    "battle spirits", "magic the gathering", "mtg ", "one piece card",
    "naruto mythos", "kryptik", "lorcana tcg",
]


def is_other_tcg(title: str, extra: str = "") -> bool:
    """True if the listing clearly belongs to another trading-card game.

    Used to drop cross-game contamination (Lorcana / Yu-Gi-Oh / Weiss Schwarz /
    Dragon Ball / ... products cross-listed inside a shop's Pokemon collection)."""
    blob = _norm(f"{title} {extra}")
    return any(k in blob for k in _OTHER_TCG_KW)
# Card collector-number signatures => a single card (e.g. "025/165", "199 / 197").
_SINGLE_NUM_RE = re.compile(r"\b\d{1,3}\s?/\s?\d{2,3}\b")


# CJK product-kind keywords (JA/KO/ZH) — checked first as they're unambiguous.
# Normalized with _norm so they match the NFKD-stripped text consistently
# (NFKD decomposes JA dakuten and KO hangul, so raw literals wouldn't match).
_CJK_DISPLAY = [_norm(k) for k in ("ボックス", "박스", "디스플레이")]          # box / display
_CJK_BOOSTER = [_norm(k) for k in ("拡張パック", "強化拡張パック", "ハイクラスパック",
                                   "パック", "부스터", "확장팩", "補充包", "扩充包",
                                   "增强包", "增強包")]


# In the JP/KR/ZH market a sealed "<set> BOX" (Latin or 박스) is a display
# (booster box of ~20-30 packs). We only honour a *bare* "box" as display for
# CJK listings, and only as a last resort (after every specific kind), so it never
# overrides an ETB / Premium Trainer Box / tin in any market.
_CJK_LANGS = {"ja", "ko", "zh"}
_BARE_BOX_RE = re.compile(r"\bbox\b")
_CJK_BARE_BOX = [_norm(k) for k in ("박스",)]   # KO 'box'; JP ボックス already in _CJK_DISPLAY


def _kind_from(t: str) -> str:
    """Classify by *containment precedence*: a product is named by the biggest
    category present, because bigger products bundle the smaller ones
    (case ⊃ display ⊃ booster; tripack/duopack ⊃ blisters/boosters; blister ⊃
    booster). So when several kind words co-occur, the largest wins.

    Order: case > display > etb > upc > bundle > coffret > minitin >
           tripack > duopack > blister > booster > accessory.

    A coffret can itself be a box of mini-tins, so coffret outranks minitin; but a
    plain "mini tin" must stay minitin, so the bare-"tin" coffret signal is
    suppressed when the only tin word is "mini tin".
    """
    has_box = (any(k in t for k in ("display", "booster box", "boite de 36",
                                    "boîte de 36", "36 boosters", "presentoir", "présentoir"))
               or any(k in t for k in _CJK_DISPLAY))
    # --- Tier A: named boxes / products (biggest first) ---
    if ("case" in t or "carton" in t) and has_box:
        return "case"
    if has_box:
        return "display"
    if ("elite trainer" in t or re.search(r"\betb\b", t)
            or "dresseur d elite" in t or "dresseur d'elite" in t or "dresseur delite" in t):
        return "etb"
    if "ultra premium" in t or re.search(r"\bupc\b", t):
        return "upc"
    if "bundle" in t or "lot de 6" in t or "pack de 6" in t or "multipack" in t:
        return "bundle"
    _bare_tin = bool(re.search(r"\btin\b", t)) and "mini tin" not in t and "mini-tin" not in t
    if ("coffret" in t or _bare_tin or "boite metal" in t or "boîte metal" in t
            or "premium collection" in t or "collection box" in t or "tin box" in t):
        return "coffret"
    if "mini tin" in t or "mini-tin" in t or "pokebox" in t:
        return "minitin"
    # --- Tier B: packs (each bundles the next; all beat blister + booster) ---
    if ("tripack" in t or "tri pack" in t or "tri-pack" in t or "3 pack" in t
            or "pack de 3" in t or "lot de 3 booster" in t or "3-pack" in t):
        return "tripack"
    if ("duopack" in t or "duo pack" in t or "duo-pack" in t or "double pack" in t
            or "twin pack" in t or "pack de 2" in t or "2-pack" in t or "2 pack" in t
            or "lot de 2 booster" in t or re.search(r"\b2 boosters?\b", t)):
        return "duopack"
    if "blister" in t:                 # blister beats booster (contains a booster)
        return "blister"
    if "booster" in t or "sachet" in t or any(k in t for k in _CJK_BOOSTER):
        return "booster"
    if any(k in t for k in ("sleeve", "protege", "classeur", "binder", "toploader", "deck box")):
        return "accessory"
    return "unknown"


def _jp_box_is_display(text_n: str, language: str) -> bool:
    """Last-resort JP rule: a CJK listing whose only box signal is a bare 'box'
    (Latin or 박스) is a display. Not applied to FR/EN, where 'box' is ambiguous."""
    if language not in _CJK_LANGS:
        return False
    return bool(_BARE_BOX_RE.search(text_n)) or any(k in text_n for k in _CJK_BARE_BOX)


def classify_kind(title: str, price=None, extra: str = "", language: str = "") -> str:
    """Classify on the title first; only fall back to description if inconclusive.

    `language` enables market-specific signals: for JA/KO/ZH a bare 'box' token is
    treated as a display (booster box) when nothing more specific matched.
    """
    title_n = _norm(_blob(title))
    k = _kind_from(title_n)
    if k == "unknown" and extra:
        k = _kind_from(_norm(f"{title} {extra}"))
    if k == "unknown" and _jp_box_is_display(title_n, language):
        return "display"
    if k == "unknown" and extra and _jp_box_is_display(_norm(f"{title} {extra}"), language):
        return "display"
    return k


# Shops whose product descriptions are reliable enough to confirm a sealed kind
# when the *title* is uninformative. Kept deliberately small and curated; a
# description signal is only ever used as a *promotion* after every singles/goodie
# guard has already passed, so it can never resurrect a single or accessory.
TRUSTED_DESC_SHOPS: set[str] = set()


def is_sealed(title: str, extra: str = "", language: str = "", shop: str = "") -> bool:
    """True if the listing is a sealed Pokemon product (not a single/goodie).

    The sealed gate is primarily checked on the TITLE, so a description that merely
    mentions e.g. "collection" can't promote a single card to a sealed kind. Two
    *narrow* relaxations:
      * JA/KO/ZH bare-'box' titles count as a sealed display (`_jp_box_is_display`);
      * for a shop in `TRUSTED_DESC_SHOPS`, a description that yields a sealed kind
        can confirm an otherwise-unclassified title.
    Both run only AFTER the banlist / goodie / single / collector-number guards, so
    they never reintroduce singles or goodies as false positives.
    """
    blob = _norm(f"{title} {extra}")
    title_n = _norm(title)
    if any(b in blob for b in _BANLIST):
        return False
    if any(k in blob for k in _OTHER_TCG_KW):   # cross-game contamination
        return False
    if any(g in blob for g in _GOODIE_KW):
        return False
    if any(d in blob for d in _DECK_KW):       # pre-built / theme / battle decks
        return False
    if any(s in blob for s in _SINGLE_KW):
        return False
    if any(s in blob for s in _CJK_SINGLE_KW):
        return False
    # "carte promo" only marks a single when nothing sealed is named, so a
    # "Display ... avec carte promo" isn't mistaken for a loose promo card.
    kind = _kind_from(title_n)
    if kind not in SEALED_KINDS and any(p in blob for p in _PROMO_SINGLE_KW):
        return False
    if _SINGLE_NUM_RE.search(title_n):
        return False
    if kind in SEALED_KINDS:
        return True
    # Relaxation 1: CJK bare-'box' display (title-level, market-specific).
    if _jp_box_is_display(title_n, language):
        return True
    # Relaxation 2: trusted shop — let the description confirm a sealed kind.
    if shop and shop in TRUSTED_DESC_SHOPS and extra:
        if _kind_from(_norm(f"{title} {extra}")) in SEALED_KINDS:
            return True
    return False


# ----------------------------------------------------------------------------- #
# Discovery helpers
# ----------------------------------------------------------------------------- #
COLLECTION_KEYWORDS = ["pokemon", "pokémon", "pokemon-tcg", "jcc-pokemon", "jcc pokemon",
                       "ecarlate", "écarlate", "epee-bouclier", "épée-bouclier",
                       "scarlet", "violet", "sword-shield", "sword & shield"]


def classify_game(blob: str) -> bool:
    """True if the product blob looks like Pokemon TCG."""
    b = _norm(blob)
    return "pokemon" in b
