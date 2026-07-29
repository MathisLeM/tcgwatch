"""Reusable cleanup pipeline for discovered rows.

Applies the same filters we used during initial curation:
- Drop rows matching JP / EN / Chinois / Anglais / Japonais / ED.2 / etc.
- Drop rows containing " US" (case-sensitive)
- Extract a valid set code (OP09..OP17, EB02/03, PRB01/02, NRT-KS-ED1, NRT-SS-ED1)
- Drop out-of-list OPTCG codes (OP01-08, EB01, ST/GC/TS/OPPB)
- Drop figurines / Funko / tin packs / anniversaries / Chinese variants
"""
import re
import pandas as pd
from urllib.parse import urlparse

VALID_SETS = {'OP09','OP10','OP11','OP12','OP13','OP14','OP15','OP16','OP17',
              'EB02','EB03','PRB01','PRB02','NRT-KS-ED1','NRT-SS-ED1'}

SUBSTR_DROP = ['kayou','(EN)','(JP)','[JP]','[EN]','JPN','rangement','Promo','Coffret',
               'Devil Fruit','Japonais','Anglais','Double Pack','Illustration Box',
               'Labyrinth','Mystery Box','Chinois','Figures','Panini']
WORD_CI_DROP = ['JP','KB','KR','JAP']
WORD_CS_DROP = ['EN']
LITERAL_CS_DROP = [' US']
ED2_DROP = ['édition 2','edition 2','2ème édition','2eme édition','2eme edition',
            '2nd edition','ed.2','ed. 2']

# --- Language filter: keep French only -------------------------------------- #
# Unambiguous non-French language words (substring match on title + url).
FOREIGN_WORDS = ['english', 'anglais', 'japanese', 'japonais', 'japon',
                 'korean', 'coréen', 'coreen', 'chinese', 'chinois',
                 'deutsch', 'allemand', 'german', 'italiano', 'italien', 'italian',
                 'español', 'espagnol', 'spanish']
# A product-slug whose LAST path segment ends in a 2-letter language code, e.g.
# play-in ".../booster-...-one-piece-ko" or wavgames ".../...-booster-en".
LANG_SUFFIX_RE = re.compile(r'-(en|jp|ja|ko|kr|cn|zh)$')
# Parenthesised language tags like "(EN)" / "(KO)" anywhere in the text.
LANG_PAREN_RE = re.compile(r'\((en|jp|ja|ko|kr|cn|zh)\)', re.IGNORECASE)
# OPK## is the Korean One Piece line code (e.g. OPK11).
KOREAN_LINE_RE = re.compile(r'\bopk\s*-?\s*\d', re.IGNORECASE)
# "VO" (version originale) = the English print; "VF" (version française) stays FR.
# Matched on title + category/description only (URL slugs are too noisy for a
# 2-letter token).
VO_RE = re.compile(r'\bvo\b', re.IGNORECASE)
# Bare JP tokens used in shop categories & descriptions, e.g. jmcards' "(JAP)".
JP_TOKEN_RE = re.compile(r'\b(jp|jap|jpn)\b', re.IGNORECASE)
# Bare "EN" tag — case-sensitive: lowercase "en" is the French preposition.
EN_TOKEN_RE = re.compile(r'\bEN\b')
# "ENG" tag — case-sensitive (English-import shops like carteonepiece tag the
# English print "... ENG"). Slug form: a bare "-eng" segment, e.g.
# ".../royal-blood-eng" or mid-slug ".../booster-eng-<barcode>".
ENG_TOKEN_RE = re.compile(r'\bENG\b')
ENG_SLUG_RE = re.compile(r'-eng(?:$|[^a-z])')

# --- Not-for-sale / placeholder products ------------------------------------ #
NOT_FOR_SALE = ['ne pas vendre', 'ne-pas-vendre', 'do not sell', 'not for sale',
                'ne pas commander', 'test produit', 'produit test']

# --- Price sanity by product type (EUR) ------------------------------------- #
# booster = single booster / blister; display = booster box (24 / 20 / 10);
# case = carton/case of multiple displays.
PRICE_RANGES = {'booster': (4.0, 40.0), 'display': (80.0, 600.0), 'case': (1000.0, 100000.0)}

NON_OPTCG_HINTS = [
    'deadzone','firefight','asterian','brood matriarch','forge father','gcps',
    'marauder','mazon labs','plague','veer-myn','tunnel ambush',
    'lorcana','pokemon','pokémon','game of thrones','bolton','greyjoy','lanister','martell',
    'mahjong','toboggan','goûter','sidewinder','katana','shogun',
    'protective case','acrylic','dés et boite','dice',
]

SET_RE = re.compile(r'(OP|EB|PRB)\s*[-\s]?\s*(\d{1,2})(?=$|[^0-9])', re.IGNORECASE)
OUT_OF_LIST_RE = re.compile(r'(OP|EB|ST|GC|TS|OPPB)\s*[-\s]?\s*(\d{1,2})', re.IGNORECASE)

FR_ALIASES = {
    "des poings vifs comme l'eclair":"OP11","des poings vifs comme l eclair":"OP11",
    "des poings vifs":"OP11",
    "l'heritage du maitre":"OP12","l'héritage du maître":"OP12",
    "heritage du maitre":"OP12","héritage du maître":"OP12",
    "successeurs":"OP13",
    "les sept de la mer d'azur":"OP14","les sept de la mer d azur":"OP14",
    "sept de la mer d'azur":"OP14","sept de la mer azur":"OP14",
    "aventure sur l'ile de dieu":"OP15","aventure sur l'île de dieu":"OP15",
    "aventure sur l ile de dieu":"OP15","ile de dieu":"OP15","île de dieu":"OP15",
    "l'heure de la bataille":"OP16","heure de la bataille":"OP16",
    "sang royal":"OP10","royal blood":"OP10",
    "les nouveaux empereurs":"OP09","nouveaux empereurs":"OP09","new emperors":"OP09",
    "anime 25th collection":"EB02","25th collection":"EB02",
    "heroines edition":"EB03","héroïnes édition":"EB03","heroines":"EB03",
}


def _slug(u):
    if not isinstance(u, str): return ""
    try:
        last = urlparse(u).path.rstrip("/").split("/")[-1]  # rstrip: woo permalinks end in '/'
        return last.lower().replace("-"," ").replace("_"," ").replace(".html","")
    except Exception:
        return ""


def _blob(row):
    return (str(row.get("title","") or "") + " " + _slug(row.get("url",""))).strip()


def _keyword_drop(blob: str) -> bool:
    for kw in SUBSTR_DROP:
        if re.search(re.escape(kw), blob, re.IGNORECASE): return True
    for kw in WORD_CI_DROP:
        if re.search(rf"\b{re.escape(kw)}\b", blob, re.IGNORECASE): return True
    for kw in WORD_CS_DROP:
        if re.search(rf"\b{re.escape(kw)}\b", blob): return True
    for kw in LITERAL_CS_DROP:
        if kw in blob: return True
    blob_l = blob.lower()
    for kw in ED2_DROP:
        if kw in blob_l: return True
    return False


def _slug_last(url: str) -> str:
    """Last path segment of a URL, lowercased, '.html' stripped (hyphens kept)."""
    if not isinstance(url, str):
        return ""
    try:
        return urlparse(url).path.rstrip("/").split("/")[-1].lower().replace(".html", "")
    except Exception:
        return ""


def is_foreign(title: str, url: str, extra: str = "") -> bool:
    """True if the product is clearly a non-French edition (EN/JP/KO/...).

    `extra` carries shop-side classification signal that is absent from the
    title/URL — the product's category / breadcrumb names and (short)
    description. This lets us catch editions whose language only shows in the
    category (e.g. lerepairetcg's "Produits Japonais", jmcards' "(JAP)") or via
    a "VO" marker (troll2jeux's OP16 "VO" = version originale = English).
    """
    blob = f"{title or ''} {url or ''} {extra or ''}".lower()
    if any(w in blob for w in FOREIGN_WORDS):
        return True
    if KOREAN_LINE_RE.search(blob):
        return True
    if LANG_PAREN_RE.search(blob):
        return True
    slug = _slug_last(url)
    if LANG_SUFFIX_RE.search(slug) or ENG_SLUG_RE.search(slug):
        return True
    # "VO" / bare language tokens: check title + extra only (not the URL slug,
    # which is too noisy for 2-letter matches).
    text = f"{title or ''} {extra or ''}"
    if VO_RE.search(text) or "version originale" in text.lower():
        return True
    if JP_TOKEN_RE.search(text) or EN_TOKEN_RE.search(text) or ENG_TOKEN_RE.search(text):
        return True
    return False


def is_not_for_sale(blob: str) -> bool:
    b = blob.lower()
    return any(k in b for k in NOT_FOR_SALE)


def product_type(blob_l: str) -> str:
    """Classify as 'case' (carton/case of displays), 'display' (booster box) or
    'booster' (single booster / blister)."""
    has_box = any(k in blob_l for k in ('display', 'boîte', 'boite', 'box'))
    if ('case' in blob_l or 'carton' in blob_l) and has_box:
        return 'case'
    if ('display' in blob_l or 'boîte de' in blob_l or 'boite de' in blob_l
            or 'box of' in blob_l or 'booster box' in blob_l or 'carton' in blob_l):
        return 'display'
    return 'booster'


def price_out_of_range(price, blob_l: str) -> bool:
    """True if a known price is outside the plausible band for its product type.
    Unknown / zero prices are kept (return False)."""
    try:
        p = float(price)
    except (TypeError, ValueError):
        return False
    if p <= 0:
        return False
    lo, hi = PRICE_RANGES[product_type(blob_l)]
    return not (lo <= p <= hi)


def _detect_fr(blob_l: str) -> bool:
    return any(m in blob_l for m in [
        "🇫🇷","[fr]","(fr)"," fr "," fr-"," - fr","français","francais",
        "chapitre","1ère édition","1ere edition","édition 1","edition 1",
        "preco","préco","premier set"])


def _extract_set(blob: str, game: str) -> str:
    blob_l = blob.lower()
    for m in SET_RE.finditer(blob):
        code = f"{m.group(1).upper()}{int(m.group(2)):02d}"
        if code in VALID_SETS: return code
    if game == "naruto_mythos":
        if not _detect_fr(blob_l): return ""
        t = blob_l.replace("ō","o")
        if "konoha" in t: return "NRT-KS-ED1"
        if "shinobi shiren" in t: return "NRT-SS-ED1"
        if "premier set" in t and "naruto mythos" in t: return "NRT-KS-ED1"
    # "The Best" premium boosters: Vol.2 => PRB02, otherwise PRB01. The volume
    # marker is often separated from "The Best" (e.g. "The Best Premium Booster
    # Vol.2"), so a plain contiguous substring alias mis-maps Vol.2 to PRB01.
    if "the best" in blob_l or "premium booster" in blob_l or "meilleur booster premium" in blob_l:
        return "PRB02" if re.search(r"vol\.?\s*0?2\b|\bv2\b", blob_l) else "PRB01"
    for alias, code in FR_ALIASES.items():
        if alias in blob_l: return code
    m = re.search(r"\bone\s*piece\s+(\d{1,2})\b", blob, re.IGNORECASE)
    if m:
        code = f"OP{int(m.group(1)):02d}"
        if code in VALID_SETS: return code
    return ""


def apply_cleanup(df: pd.DataFrame) -> pd.DataFrame:
    """Return a new DataFrame with bad rows dropped and `set` column populated."""
    if df.empty:
        df = df.copy(); df["set"] = ""; return df
    out = df.copy()
    out["_blob"] = out.apply(_blob, axis=1)
    out = out[~out["_blob"].apply(_keyword_drop)].copy()
    if out.empty:
        return out.drop(columns=["_blob"], errors="ignore")
    # Drop non-French editions and not-for-sale / placeholder products. The
    # 'category' column (when present) carries shop-side classification — product
    # category / breadcrumb names + short description — so language markers that
    # only appear there (e.g. "Produits Japonais") still get caught.
    out = out[~out.apply(lambda r: is_foreign(str(r.get("title","") or ""),
                                              str(r.get("url","") or ""),
                                              str(r.get("category","") or "")), axis=1)].copy()
    out = out[~out["_blob"].apply(is_not_for_sale)].copy()
    if out.empty:
        return out.drop(columns=["_blob"], errors="ignore")
    out["set"] = out.apply(lambda r: _extract_set(r["_blob"], r.get("game","")), axis=1)

    def should_drop(row):
        blob_l = row["_blob"].lower()
        if row["set"] in VALID_SETS: return False
        if any(h in blob_l for h in NON_OPTCG_HINTS): return True
        if OUT_OF_LIST_RE.search(row["_blob"]): return True
        if "anniversary" in blob_l or "anniversaire" in blob_l or "premium bandai" in blob_l: return True
        if "funko" in blob_l or "figurine" in blob_l: return True
        if "tin pack" in blob_l or "protection souple" in blob_l: return True
        if row.get("game") == "naruto_mythos" and row["set"] == "": return True
        if row.get("game") == "optcg" and row["set"] == "": return True
        return False

    out = out[~out.apply(should_drop, axis=1)].copy()
    # Price sanity: drop products whose price is implausible for their type
    # (e.g. a "display" priced 7.42€ is a mislabel). Unknown prices are kept.
    if not out.empty and "price_min" in out.columns:
        out = out[~out.apply(
            lambda r: price_out_of_range(r.get("price_min"), r["_blob"].lower()), axis=1)].copy()
    out = out.drop(columns=["_blob"], errors="ignore")
    # Position 'set' column right after 'title' if present
    if "set" in out.columns and "title" in out.columns:
        cols = list(out.columns)
        cols.insert(cols.index("title") + 1, cols.pop(cols.index("set")))
        out = out[cols]
    return out
