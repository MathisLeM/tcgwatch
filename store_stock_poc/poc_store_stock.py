"""
PoC de faisabilite - recuperation du stock par magasin (Fnac / King Jouet / Cultura)
====================================================================================

Contexte
--------
Ce script est un test de faisabilite ISOLE : il ne fait partie du projet TCG_Scrapper
et n'importe rien depuis celui-ci. Objectif : prouver qu'on peut recuperer, pour un
produit (booster One Piece), la disponibilite en stock magasin par magasin, sans
navigateur (juste `requests`), pour 3 enseignes prioritaires : Fnac, King Jouet, Cultura.

Toutes les requetes ci-dessous ont ete identifiees et validees manuellement en
inspectant le trafic reseau reel des sites (juillet 2026) via un navigateur, sur un
produit reel : boosters One Piece Card Game. Ce fichier reproduit ces requetes en
HTTP pur.

IMPORTANT : ce script doit etre execute depuis une machine avec un acces internet
normal (le sandbox de developpement utilise ici n'a pas d'acces internet general).

Dependances : requests, beautifulsoup4 (deja dans requirements.txt du projet).

    pip install requests beautifulsoup4

Produits de test (reels, trouves le 14/07/2026) :
  - Fnac       : prid=22385245  "Carte a collectionner One Piece Les Sept de la
                 Mer d'Azur Booster Blister"  (5,99 EUR)
  - King Jouet : product_uuid=36bec2b1-8bce-49d8-b681-580b6d2c7efa ; ref=999428
                 "Cartes One Piece Booster OP12 L'heritage du maitre"  (6,99 EUR)
  - Cultura    : sku=12777658  "Booster One Piece : les Sept de la Mer d'Azur - Bandai"
                 (5,99 EUR)
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class StoreStock:
    retailer: str
    store_name: str
    store_address: str | None
    available: bool
    raw_status: str


# ---------------------------------------------------------------------------
# 1) FNAC
# ---------------------------------------------------------------------------
# Mecanisme observe :
#   GET  https://www.fnac.com/api/reference/rest/v3/geocoding?term=<ville_ou_cp>
#        -> geocode le texte saisi en (latitude, longitude)
#   POST https://www.fnac.com/nav/api/StorePickup/SearchStore
#        body (form url-encoded) :
#          inputValue, latitude, longitude, prid, catalog=1,
#          onShlef=false, isRetreatOneHour=false,
#          formId=<peut etre une valeur bidon, non verifiee cote serveur>,
#          offerref=00000000-0000-0000-0000-000000000000
#        -> renvoie un fragment HTML avec ~30 magasins tries par distance,
#           chacun avec statut "En rayon" (dispo) / "Indisponible", adresse, id
#           magasin (ex: divStoreDetail_43 -> id 43).
# Limite : ~30 magasins par requete (teste : 30 li.liStore, 7 "En rayon" + 23
# "Indisponible" sur une recherche 69001) -> il faudra balayer plusieurs codes
# postaux / departements pour couvrir tout le reseau Fnac (~700+ magasins).

FNAC_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def fnac_geocode(session: requests.Session, term: str) -> tuple[str, str]:
    r = session.get(
        "https://www.fnac.com/api/reference/rest/v3/geocoding",
        params={"term": term},
        headers=FNAC_HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    # Reponse observee : {"Latitude": 45.77, "Longitude": 4.82, "Status": 1}
    return str(data["Latitude"]), str(data["Longitude"])


def fnac_check_stock(prid: str, postal_code: str, max_stores: int = 30) -> list[StoreStock]:
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    # Warm-up : necessaire pour obtenir les cookies de session standard.
    session.get(f"https://www.fnac.com/a{prid}", timeout=20)

    lat, lon = fnac_geocode(session, postal_code)

    body = {
        "inputValue": postal_code,
        "latitude": lat,
        "longitude": lon,
        "prid": prid,
        "catalog": "1",
        "onShlef": "false",
        "isRetreatOneHour": "false",
        "formId": "0" * 32,  # non verifie cote serveur (teste manuellement)
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
    results: list[StoreStock] = []
    for li in soup.select("li.liStore")[:max_stores]:
        name_span = li.select_one(".storeName")
        name = name_span.get_text(strip=True) if name_span else "?"
        status_span = li.select_one(".status-color")
        status_text = status_span.get_text(strip=True) if status_span else "?"
        # Le statut le plus fiable est le texte lui-meme ("En rayon" vs
        # "Indisponible") ; le parent porte aussi une classe ColorStatus_0/2
        # mais le texte est plus stable dans le temps.
        addr_div = li.select_one(".store-adr")
        address = addr_div.get_text(" ", strip=True) if addr_div else None
        results.append(
            StoreStock(
                retailer="Fnac",
                store_name=name,
                store_address=address,
                available="en rayon" in status_text.lower(),
                raw_status=status_text,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 2) KING JOUET
# ---------------------------------------------------------------------------
# Mecanisme observe : API REST/JSON propre, aucune authentification necessaire.
#   GET https://www.king-jouet.com/api/store/search/postal-code?query=<cp>
#       -> jusqu'a 5 magasins proches : {guid, code, label, postalCode, city,
#          streetAddress, openingHours}
#   GET https://www.king-jouet.com/api/product/<product_uuid>/availability-in-stores/
#           <guid1>_<guid2>_..._<guidN>
#       -> [{storeGuid, availability: "Non disponible"|"Retrait en 2h"|...,
#            isStoreAvailable}]
#
# Le product_uuid n'est pas dans l'URL produit (qui utilise une ref numerique,
# ex: ref-999428) : il est embarque dans le HTML de la page produit (payload
# Nuxt) juste avant la ref numerique. On l'extrait par regex.
# Limite : 5 magasins par requete -> balayage necessaire (comme Fnac).

KJ_HEADERS = {"User-Agent": UA, "Accept": "application/json"}

UUID_RE = re.compile(
    r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"\s*,\s*"(\d+)"'
)


def kingjouet_extract_product_uuid(product_url: str, expected_ref: str) -> str | None:
    r = requests.get(product_url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    for uuid, ref in UUID_RE.findall(r.text):
        if ref == expected_ref:
            return uuid
    return None


def kingjouet_check_stock(product_uuid: str, postal_code: str) -> list[StoreStock]:
    session = requests.Session()
    session.headers.update(KJ_HEADERS)

    r = session.get(
        "https://www.king-jouet.com/api/store/search/postal-code",
        params={"query": postal_code},
        timeout=20,
    )
    r.raise_for_status()
    stores = r.json()
    if not stores:
        return []

    guids = "_".join(s["guid"] for s in stores)
    r2 = session.get(
        f"https://www.king-jouet.com/api/product/{product_uuid}/availability-in-stores/{guids}",
        timeout=20,
    )
    r2.raise_for_status()
    availability = {a["storeGuid"]: a for a in r2.json()}

    results: list[StoreStock] = []
    for s in stores:
        a = availability.get(s["guid"], {})
        status = a.get("availability", "?")
        results.append(
            StoreStock(
                retailer="King Jouet",
                store_name=s["label"],
                store_address=f"{s['streetAddress']}, {s['postalCode']} {s['city']}",
                available=status not in ("Non disponible", "?"),
                raw_status=status,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 3) CULTURA
# ---------------------------------------------------------------------------
# Mecanisme observe : backend Magento GraphQL (endpoint public, introspection
# activee -> schema explorable).
#   POST https://www.cultura.com/magento/graphql   body: {"query": "..."}
#
#   a) Annuaire complet des magasins EN UNE SEULE requete (tres bonne nouvelle -
#      contrairement a Fnac/King Jouet il n'y a pas besoin de balayer les codes
#      postaux pour obtenir juste la LISTE des magasins) :
#        query { stores(limit: 200, country_code: "FR") {
#          total_count items { id seller_code name url_key position { latitude longitude }
#          opening_hours { dayofweek start_time end_time } } } }
#      -> 118 magasins renvoyes en un appel (limit=200 suffit largement).
#
#   b) Stock par magasin pour un produit (sku) :
#        query { products(filter: {sku: {eq: "<sku>"}}) {
#          items { sku stock_item_extra { offer { seller_code front_availability qty } } } } }
#      Ce champ "offer" ne prend pas d'argument, et POINT IMPORTANT verifie
#      pendant ce test : le sous-ensemble de magasins renvoye (9 dans nos essais)
#      ne change PAS quand on fait varier le parametre "search" de la requete
#      stores(), ni quand on modifie manuellement le cookie "preferred_shop".
#      Il semble determine par un mecanisme cote serveur distinct (tres
#      probablement lie a la geolocalisation IP et/ou a un cookie type
#      "oss-eresa-cultura" - present mais pas encore decode). Conclusion :
#      la volumetrie/le principe (stock reel par magasin, via seller_code) est
#      confirme et fonctionne sans navigateur, MAIS le mecanisme exact pour
#      cibler une region donnee (plutot que la region par defaut du serveur)
#      n'est pas encore perce -> a approfondir avant de batir le balayage
#      national (cf. section "prochaine etape" plus bas).
#      A noter aussi : Cultura est protege par DataDome (cookie "datadome"
#      detecte) -> a surveiller pour la version production (risque de blocage
#      plus fort qu'avec Fnac/King Jouet, qui n'ont pas montre ce signal).

CULTURA_GRAPHQL = "https://www.cultura.com/magento/graphql"
CULTURA_HEADERS = {"User-Agent": UA, "Content-Type": "application/json"}


def cultura_list_all_stores(session: requests.Session | None = None) -> list[dict]:
    session = session or requests.Session()
    query = (
        "query{stores(limit:200, country_code:\"FR\"){total_count items{"
        "id seller_code name url_key position{latitude longitude}}}}"
    )
    r = session.post(
        CULTURA_GRAPHQL, json={"query": query}, headers=CULTURA_HEADERS, timeout=20
    )
    r.raise_for_status()
    return r.json()["data"]["stores"]["items"]


def cultura_nearby_store_codes(session: requests.Session, postal_code: str) -> list[dict]:
    query = (
        "query{stores(search:\"%s\"){total_count items{id seller_code name}}}"
        % postal_code
    )
    r = session.post(
        CULTURA_GRAPHQL, json={"query": query}, headers=CULTURA_HEADERS, timeout=20
    )
    r.raise_for_status()
    return r.json()["data"]["stores"]["items"]


def cultura_check_stock(sku: str, postal_code: str) -> list[StoreStock]:
    session = requests.Session()
    nearby = cultura_nearby_store_codes(session, postal_code)
    code_to_store = {s["seller_code"]: s for s in nearby}

    query = (
        'query{products(filter:{sku:{eq:"%s"}}){items{sku '
        "stock_item_extra{offer{seller_code front_availability qty}}}}}" % sku
    )
    r = session.post(
        CULTURA_GRAPHQL, json={"query": query}, headers=CULTURA_HEADERS, timeout=20
    )
    r.raise_for_status()
    items = r.json()["data"]["products"]["items"]
    if not items:
        return []
    offers = items[0]["stock_item_extra"]["offer"] or []

    results: list[StoreStock] = []
    for o in offers:
        store = code_to_store.get(o["seller_code"], {"name": o["seller_code"]})
        results.append(
            StoreStock(
                retailer="Cultura",
                store_name=store.get("name", o["seller_code"]),
                store_address=None,
                available=o["front_availability"] == "available",
                raw_status=f'{o["front_availability"]} (qty~{o["qty"]})',
            )
        )
    return results


# ---------------------------------------------------------------------------
# Test de faisabilite
# ---------------------------------------------------------------------------

def main():
    postal_code = sys.argv[1] if len(sys.argv) > 1 else "69001"
    print(f"=== Test de faisabilite stock magasin (code postal : {postal_code}) ===\n")

    print("--- Fnac ---")
    try:
        for s in fnac_check_stock(prid="22385245", postal_code=postal_code):
            flag = "OK" if s.available else "--"
            print(f"[{flag}] {s.store_name:35s} {s.raw_status}")
    except Exception as e:
        print(f"ECHEC Fnac : {e}")

    print("\n--- King Jouet ---")
    try:
        product_url = (
            "https://www.king-jouet.com/jeu-jouet/jeux-societes/cartes-a-collectionner/"
            "ref-999428-cartes-one-piece-booster-op12-l-heritage-du-maitre.htm"
        )
        uuid = kingjouet_extract_product_uuid(product_url, expected_ref="999428")
        uuid = uuid or "36bec2b1-8bce-49d8-b681-580b6d2c7efa"  # fallback connu
        for s in kingjouet_check_stock(uuid, postal_code):
            flag = "OK" if s.available else "--"
            print(f"[{flag}] {s.store_name:35s} {s.raw_status}")
    except Exception as e:
        print(f"ECHEC King Jouet : {e}")

    print("\n--- Cultura ---")
    try:
        for s in cultura_check_stock(sku="12777658", postal_code=postal_code):
            flag = "OK" if s.available else "--"
            print(f"[{flag}] {s.store_name:35s} {s.raw_status}")
    except Exception as e:
        print(f"ECHEC Cultura : {e}")

    print("\n--- Cultura : annuaire complet des magasins (1 seul appel) ---")
    try:
        stores = cultura_list_all_stores()
        print(f"{len(stores)} magasins Cultura recuperes en un seul appel GraphQL.")
    except Exception as e:
        print(f"ECHEC annuaire Cultura : {e}")


if __name__ == "__main__":
    main()
