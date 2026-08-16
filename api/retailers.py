"""Registry of big retail chains shown in the "Grandes enseignes" overlay.

Curated in code (not the DB) because it also lists chains we *can't* scrape yet
(shown greyed-out in the UI). `platform` links a live retailer to its rows in the
`products` table (platform column). `status`:
  - "live"    : scraped, products available
  - "soon"    : technically feasible, not built yet
  - "blocked" : hard anti-bot (DataDome/Akamai) — not scraped, shown disabled
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Retailer(BaseModel):
    id: str                      # slug, e.g. "micromania"
    name: str
    platform: Optional[str] = None   # products.platform for live retailers
    status: str                  # live | soon | blocked
    has_store_stock: bool = False    # exposes per-store availability we can read
    note: Optional[str] = None


RETAILERS: list[Retailer] = [
    # Le scraping Micromania (stealth browser) et le stock par magasin marchent en
    # POC mais ne sont pas assez fiables pour être exposés — repassés en "soon" en
    # attendant la reprise du chantier "grandes enseignes". `platform` reste
    # renseigné pour que l'overlay affiche le volume déjà collecté.
    Retailer(id="micromania", name="Micromania", platform="micromania",
             status="soon", has_store_stock=False,
             note="Scraping + stock magasin en POC — fiabilité à consolider"),
    Retailer(id="smythstoys", name="Smyths Toys", status="soon",
             note="Incapsula — même approche que Micromania, à valider"),
    Retailer(id="fnac", name="Fnac", status="blocked", note="Akamai Bot Manager"),
    Retailer(id="king-jouet", name="King Jouet", status="blocked", note="Cloudflare + DataDome"),
    Retailer(id="cultura", name="Cultura", status="blocked", note="Cloudflare + DataDome"),
]

_BY_ID = {r.id: r for r in RETAILERS}
_BY_PLATFORM = {r.platform: r for r in RETAILERS if r.platform}


def get_by_id(rid: str) -> Optional[Retailer]:
    return _BY_ID.get(rid)


def get_by_platform(platform: str) -> Optional[Retailer]:
    return _BY_PLATFORM.get(platform)
