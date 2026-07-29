"""
Fonctions d'acces aux stocks magasin (Fnac / King Jouet / Cultura), limitees a
l'Île-de-France, pour le dashboard POC.

Reprend les mecanismes valides dans poc_store_stock.py, avec en plus :
  - un filtrage sur les codes postaux IDF (75/77/78/91/92/93/94/95)
  - pour Cultura : un calcul de distance (haversine) contre l'annuaire statique
    IDF (cf. idf_dashboard_catalog.CULTURA_IDF_STORES), car l'API stock de
    Cultura ne cible pas la zone geographique demandee (cf. limitation notee
    dans FINDINGS.md) - on affiche donc les magasins IDF les plus proches et on
    tente une correspondance avec ce que l'API renvoie reellement.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from idf_dashboard_catalog import CULTURA_IDF_STORES, is_idf_postcode

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class StoreResult:
    retailer: str
    store_name: str
    postcode: str
    city: str
    available: bool
    raw_status: str
    distance_km: float | None = None


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Geocodage generique (reutilise l'API publique Fnac, qui accepte code postal
# OU ville en texte libre) - sert de geocodeur commun a tout le dashboard.
# ---------------------------------------------------------------------------

def geocode(term: str) -> tuple[float, float]:
    r = requests.get(
        "https://www.fnac.com/api/reference/rest/v3/geocoding",
        params={"term": term},
        headers={"User-Agent": UA},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return float(data["Latitude"]), float(data["Longitude"])


# ---------------------------------------------------------------------------
# FNAC
# ---------------------------------------------------------------------------

FNAC_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def fnac_idf_stock(prid: str, user_term: str, max_results: int = 8) -> list[StoreResult]:
    if not prid:
        return []
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    session.get(f"https://www.fnac.com/a{prid}", timeout=20)

    lat, lon = geocode(user_term)

    body = {
        "inputValue": user_term,
        "latitude": str(lat),
        "longitude": str(lon),
        "prid": prid,
        "catalog": "1",
        "onShlef": "false",
        "isRetreatOneHour": "false",
        "formId": "0" * 32,
        "offerref": "00000000-0000-0000-0000-000000000000",
    }
    r = session.post(
        "https://www.fnac.com/nav/api/StorePickup/SearchStore",
        data=body,
        headers=FNAC_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    results: list[StoreResult] = []
    for li in soup.select("li.liStore"):
        name_span = li.select_one(".storeName")
        name = name_span.get_text(strip=True) if name_span else "?"
        status_span = li.select_one(".status-color")
        status_text = status_span.get_text(strip=True) if status_span else "?"
        addr_div = li.select_one(".store-adr")
        addr_text = addr_div.get_text(" ", strip=True) if addr_div else ""
        m = re.search(r"(\d{5})\s*$", addr_text)
        postcode = m.group(1) if m else ""
        if not is_idf_postcode(postcode):
            continue
        city = addr_text.rsplit(postcode, 1)[0].strip().split(" ")[-1] if postcode else ""
        results.append(
            StoreResult(
                retailer="Fnac",
                store_name=name,
                postcode=postcode,
                city=city,
                available="en rayon" in status_text.lower(),
                raw_status=status_text,
            )
        )
        if len(results) >= max_results:
            break
    return results


# ---------------------------------------------------------------------------
# KING JOUET
# ---------------------------------------------------------------------------

KJ_HEADERS = {"User-Agent": UA, "Accept": "application/json"}


def kingjouet_idf_stock(product_uuid: str, user_term: str, max_results: int = 8) -> list[StoreResult]:
    if not product_uuid:
        return []
    session = requests.Session()
    session.headers.update(KJ_HEADERS)

    r = session.get(
        "https://www.king-jouet.com/api/store/search/postal-code",
        params={"query": user_term},
        timeout=20,
    )
    r.raise_for_status()
    stores = [s for s in r.json() if is_idf_postcode(str(s.get("postalCode", "")))]
    if not stores:
        return []
    stores = stores[:max_results]

    guids = "_".join(s["guid"] for s in stores)
    r2 = session.get(
        f"https://www.king-jouet.com/api/product/{product_uuid}/availability-in-stores/{guids}",
        timeout=20,
    )
    r2.raise_for_status()
    availability = {a["storeGuid"]: a for a in r2.json()}

    results: list[StoreResult] = []
    for s in stores:
        a = availability.get(s["guid"], {})
        status = a.get("availability", "?")
        results.append(
            StoreResult(
                retailer="King Jouet",
                store_name=s["label"],
                postcode=str(s.get("postalCode", "")),
                city=s.get("city", ""),
                available=status not in ("Non disponible", "?"),
                raw_status=status,
            )
        )
    return results


# ---------------------------------------------------------------------------
# CULTURA
# ---------------------------------------------------------------------------

CULTURA_GRAPHQL = "https://www.cultura.com/magento/graphql"
CULTURA_HEADERS = {"User-Agent": UA, "Content-Type": "application/json"}


def cultura_idf_stock(sku: str, user_lat: float, user_lon: float, max_results: int = 8) -> list[StoreResult]:
    """
    Limitation connue (cf. FINDINGS.md) : l'API stock de Cultura ne cible pas
    une zone geographique donnee - elle renvoie le stock pour un ensemble de
    magasins fixe cote serveur (probablement lie a la geolocalisation IP).
    On affiche donc les magasins IDF les plus proches de l'utilisateur
    (distance calculee nous-memes), et on ne renseigne le statut de stock que
    pour ceux qui apparaissent dans la reponse de l'API (les autres sont
    marques "non verifiable").
    """
    if not sku:
        return []

    nearest = sorted(
        CULTURA_IDF_STORES,
        key=lambda s: haversine_km(user_lat, user_lon, s["lat"], s["lon"]),
    )[:max_results]

    session = requests.Session()
    query = (
        'query{products(filter:{sku:{eq:"%s"}}){items{sku '
        'stock_item_extra{offer{seller_code front_availability qty}}}}}' % sku
    )
    offers_by_code = {}
    try:
        r = session.post(
            CULTURA_GRAPHQL, json={"query": query}, headers=CULTURA_HEADERS, timeout=20
        )
        r.raise_for_status()
        items = r.json().get("data", {}).get("products", {}).get("items", [])
        if items:
            offers = items[0]["stock_item_extra"]["offer"] or []
            offers_by_code = {o["seller_code"]: o for o in offers}
    except Exception:
        pass

    results: list[StoreResult] = []
    for s in nearest:
        dist = haversine_km(user_lat, user_lon, s["lat"], s["lon"])
        offer = offers_by_code.get(s["seller_code"])
        if offer is None:
            status = "Non vérifiable (limite API Cultura)"
            available = False
        else:
            status = f'{offer["front_availability"]} (qty~{offer["qty"]})'
            available = offer["front_availability"] == "available"
        results.append(
            StoreResult(
                retailer="Cultura",
                store_name=s["name"],
                postcode=s["postcode"],
                city=s["city"],
                available=available,
                raw_status=status,
                distance_km=round(dist, 1),
            )
        )
    return results
