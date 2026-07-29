"""Paths and constants shared across the scraper."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"   # TCGdex set tables, etc.
IMAGES_DIR = ROOT / "images"
DB_PATH = DATA_DIR / "tcg_stock.sqlite"

# Supported games (the top-left dashboard toggle) and languages.
GAMES = ["optcg", "pokemon"]
# Language codes used across the DB. OPTCG/Naruto are FR-only; Pokemon is multi-lang.
LANGUAGES = ["fr", "en", "ja", "ko", "zh"]
LANGUAGE_NAMES = {"fr": "Français", "en": "English", "ja": "日本語",
                  "ko": "한국어", "zh": "中文"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
REQUEST_TIMEOUT = 15
PER_DOMAIN_DELAY = 1.0  # seconds between requests to same domain
