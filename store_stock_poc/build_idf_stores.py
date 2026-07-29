"""
Construction de l'annuaire des magasins Île-de-France (Fnac / King Jouet / Cultura).

Constat (14/07/2026, cette session) : les endpoints valides dans poc_store_stock.py
sont proteges par DataDome et rejettent TOUT client HTTP non-navigateur (python
requests ET curl_cffi impersonation Chrome, meme depuis une IP residentielle).
Le POC initial les avait valides depuis un vrai navigateur - d'ou l'ecart.

Solution : le meme pattern que Micromania (api/services/store_inventory.py) -
scraper.stealth_browser (Playwright) charge une page du site (DataDome pose son
cookie apres execution de son JS), puis on appelle les APIs internes via fetch()
DEPUIS le contexte de la page, qui porte les cookies et le fingerprint valides.

Usage (depuis la racine TCG_Scrapper) :
    python store_stock_poc/build_idf_stores.py kj        # King Jouet seul
    python store_stock_poc/build_idf_stores.py fnac      # Fnac seul
    python store_stock_poc/build_idf_stores.py cultura   # Cultura + test hypothese geo
    python store_stock_poc/build_idf_stores.py all

Sortie : store_stock_poc/idf_stores.json (fusionne au fil des runs).
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from bs4 import BeautifulSoup

from scraper.stealth_browser import stealth_page, goto, settle
from idf_dashboard_catalog import CULTURA_IDF_STORES, is_idf_postcode

OUT_PATH = HERE / "idf_stores.json"

# Delai de politesse entre deux fetch dans la page (secondes).
DELAY = 1.2

# Codes postaux de balayage. Fnac renvoie ~30 magasins/reponse -> peu de points
# suffisent. King Jouet n'en renvoie que 5 -> grille plus dense.
FNAC_SWEEP = ["75001", "77000", "77700", "78000", "78200", "91000", "95000", "93600", "94000"]
KJ_SWEEP = [
    "75001", "75012", "75017",
    "77000", "77100", "77300", "77500", "77700",
    "78000", "78100", "78200", "78310", "78500",
    "91000", "91100", "91300", "91400", "91800",
    "92100", "92230", "92400",
    "93100", "93200", "93600",
    "94000", "94120", "94320",
    "95000", "95100", "95200", "95500",
]

FETCH_JSON_JS = """async (u) => {
    const r = await fetch(u, {headers: {'Accept': 'application/json',
                                        'X-Requested-With': 'XMLHttpRequest'}});
    const text = await r.text();
    return {status: r.status, text};
}"""

FETCH_FORM_POST_JS = """async ({url, body}) => {
    const r = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                  'Accept': 'text/html, */*; q=0.01',
                  'X-Requested-With': 'XMLHttpRequest'},
        body: new URLSearchParams(body).toString(),
    });
    const text = await r.text();
    return {status: r.status, text};
}"""

FETCH_GRAPHQL_JS = """async (q) => {
    const r = await fetch('/magento/graphql', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({query: q}),
    });
    const text = await r.text();
    return {status: r.status, text};
}"""


def _load_out() -> dict:
    if OUT_PATH.exists():
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    return {}


def _save_out(key: str, stores: list[dict]) -> None:
    data = _load_out()
    data[key] = stores
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {len(stores)} magasins '{key}' ecrits dans {OUT_PATH.name}")


# ---------------------------------------------------------------------------
# KING JOUET
# ---------------------------------------------------------------------------

def build_kingjouet() -> list[dict]:
    print("=== King Jouet : balayage de", len(KJ_SWEEP), "codes postaux ===")
    stores: dict[str, dict] = {}
    with stealth_page() as (page, _ctx):
        goto(page, "https://www.king-jouet.com/")
        settle(page)
        html = page.content()
        if len(html) < 5000:
            print("!! Page d'accueil suspecte (challenge ?) len=", len(html))
        for i, cp in enumerate(KJ_SWEEP):
            res = page.evaluate(
                FETCH_JSON_JS,
                f"/api/store/search/postal-code?query={cp}",
            )
            if res["status"] != 200:
                print(f"  [{cp}] HTTP {res['status']} - {res['text'][:80]}")
                time.sleep(DELAY)
                continue
            try:
                batch = json.loads(res["text"])
            except json.JSONDecodeError:
                print(f"  [{cp}] reponse non-JSON: {res['text'][:80]}")
                time.sleep(DELAY)
                continue
            new = 0
            for s in batch:
                guid = s.get("guid")
                if not guid or guid in stores:
                    continue
                stores[guid] = s
                new += 1
            print(f"  [{cp}] {len(batch)} magasins, {new} nouveaux (total {len(stores)})")
            time.sleep(DELAY)

    # Premier magasin brut : utile pour voir les champs disponibles (lat/lon ?)
    if stores:
        first = next(iter(stores.values()))
        print("Champs disponibles:", sorted(first.keys()))

    idf = []
    for s in stores.values():
        cp = str(s.get("postalCode", ""))
        if not is_idf_postcode(cp):
            continue
        idf.append({
            "retailer": "kingjouet",
            "store_id": s.get("guid"),
            "code": s.get("code"),
            "name": s.get("label"),
            "address": s.get("streetAddress"),
            "postcode": cp,
            "city": s.get("city"),
            "lat": s.get("latitude"),
            "lon": s.get("longitude"),
        })
    idf.sort(key=lambda x: (x["postcode"], x["name"] or ""))
    print(f"King Jouet : {len(stores)} magasins uniques vus, {len(idf)} en IDF")
    return idf


# ---------------------------------------------------------------------------
# FNAC
# ---------------------------------------------------------------------------

FNAC_PRID = "22385245"  # produit reel (booster OP14) requis par SearchStore


def build_fnac() -> list[dict]:
    print("=== Fnac : balayage de", len(FNAC_SWEEP), "points geo ===")
    stores: dict[str, dict] = {}
    with stealth_page() as (page, _ctx):
        goto(page, f"https://www.fnac.com/a{FNAC_PRID}")
        settle(page)
        html = page.content()
        if len(html) < 5000:
            print("!! Page produit suspecte (challenge ?) len=", len(html))
        for cp in FNAC_SWEEP:
            geo = page.evaluate(
                FETCH_JSON_JS,
                f"/api/reference/rest/v3/geocoding?term={cp}",
            )
            if geo["status"] != 200:
                print(f"  [{cp}] geocoding HTTP {geo['status']}")
                time.sleep(DELAY)
                continue
            g = json.loads(geo["text"])
            lat, lon = g.get("Latitude"), g.get("Longitude")
            res = page.evaluate(FETCH_FORM_POST_JS, {
                "url": "/nav/api/StorePickup/SearchStore",
                "body": {
                    "inputValue": cp,
                    "latitude": str(lat),
                    "longitude": str(lon),
                    "prid": FNAC_PRID,
                    "catalog": "1",
                    "onShlef": "false",
                    "isRetreatOneHour": "false",
                    "formId": "0" * 32,
                    "offerref": "00000000-0000-0000-0000-000000000000",
                },
            })
            if res["status"] != 200:
                print(f"  [{cp}] SearchStore HTTP {res['status']} - {res['text'][:80]}")
                time.sleep(DELAY)
                continue
            soup = BeautifulSoup(res["text"], "lxml")
            new = 0
            batch = soup.select("li.liStore")
            for li in batch:
                sid = None
                detail = li.select_one("[id^=divStoreDetail_]")
                node = detail if detail is not None else li
                m = re.search(r"divStoreDetail_(\d+)", str(node.get("id", "")) or str(li))
                if m:
                    sid = m.group(1)
                name_span = li.select_one(".storeName")
                name = name_span.get_text(strip=True) if name_span else None
                addr_div = li.select_one(".store-adr")
                addr = addr_div.get_text(" ", strip=True) if addr_div else ""
                key = sid or name or addr
                if not key or key in stores:
                    continue
                stores[key] = {"store_id": sid, "name": name, "address_raw": addr}
                new += 1
            print(f"  [{cp}] {len(batch)} magasins, {new} nouveaux (total {len(stores)})")
            time.sleep(DELAY)

    idf = []
    for s in stores.values():
        addr = s["address_raw"] or ""
        m = re.search(r"(\d{5})(?!.*\d{5})", addr)  # dernier CP de l'adresse
        cp = m.group(1) if m else ""
        if not is_idf_postcode(cp):
            continue
        city = addr[m.end():].strip(" ,") if m else ""
        street = addr[: m.start()].strip(" ,") if m else addr
        idf.append({
            "retailer": "fnac",
            "store_id": s["store_id"],
            "name": s["name"],
            "address": street,
            "postcode": cp,
            "city": city,
            "lat": None,
            "lon": None,
        })
    idf.sort(key=lambda x: (x["postcode"], x["name"] or ""))
    print(f"Fnac : {len(stores)} magasins uniques vus, {len(idf)} en IDF")
    return idf


# ---------------------------------------------------------------------------
# CULTURA (+ test de l'hypothese "sous-ensemble par defaut = pres de l'IP")
# ---------------------------------------------------------------------------

CULTURA_TEST_SKU = "12777658"  # booster OP14, present chez Cultura

CULTURA_STORES_QUERY_RICH = (
    'query{stores(limit:200, country_code:"FR"){total_count items{'
    "id seller_code name url_key position{latitude longitude} "
    "address{postcode city} }}}"
)
CULTURA_STORES_QUERY_BASIC = (
    'query{stores(limit:200, country_code:"FR"){total_count items{'
    "id seller_code name url_key position{latitude longitude} }}}"
)


def build_cultura() -> list[dict]:
    print("=== Cultura : annuaire (1 appel) + test hypothese geo ===")
    idf: list[dict] = []
    with stealth_page() as (page, _ctx):
        goto(page, "https://www.cultura.com/")
        settle(page)
        html = page.content()
        if len(html) < 5000:
            print("!! Page d'accueil suspecte (challenge ?) len=", len(html))

        res = page.evaluate(FETCH_GRAPHQL_JS, CULTURA_STORES_QUERY_RICH)
        data = json.loads(res["text"]) if res["status"] == 200 else {}
        if res["status"] != 200 or data.get("errors"):
            print("  requete riche refusee, fallback basique",
                  (data.get("errors") or [{}])[0].get("message", res["status"]))
            time.sleep(DELAY)
            res = page.evaluate(FETCH_GRAPHQL_JS, CULTURA_STORES_QUERY_BASIC)
            data = json.loads(res["text"]) if res["status"] == 200 else {}
        items = (data.get("data", {}).get("stores", {}) or {}).get("items", []) or []
        print(f"  {len(items)} magasins France recuperes")

        static_by_code = {s["seller_code"]: s for s in CULTURA_IDF_STORES}
        for s in items:
            addr = s.get("address") or {}
            cp = str(addr.get("postcode") or
                     static_by_code.get(s.get("seller_code"), {}).get("postcode", ""))
            if not is_idf_postcode(cp):
                continue
            pos = s.get("position") or {}
            static = static_by_code.get(s.get("seller_code"), {})
            idf.append({
                "retailer": "cultura",
                "store_id": str(s.get("id")),
                "seller_code": s.get("seller_code"),
                "name": s.get("name"),
                "address": None,
                "postcode": cp,
                "city": addr.get("city") or static.get("city"),
                "lat": pos.get("latitude") or static.get("lat"),
                "lon": pos.get("longitude") or static.get("lon"),
            })
        idf.sort(key=lambda x: (x["postcode"], x["name"] or ""))
        print(f"Cultura : {len(idf)} magasins en IDF")

        # --- Test hypothese : quels magasins l'API stock renvoie-t-elle ici ? ---
        time.sleep(DELAY)
        q = ('query{products(filter:{sku:{eq:"%s"}}){items{sku '
             "stock_item_extra{offer{seller_code front_availability qty}}}}}"
             % CULTURA_TEST_SKU)
        res = page.evaluate(FETCH_GRAPHQL_JS, q)
        if res["status"] == 200:
            d = json.loads(res["text"])
            prods = (d.get("data", {}).get("products", {}) or {}).get("items", [])
            offers = (prods[0]["stock_item_extra"]["offer"] or []) if prods else []
            codes = [o["seller_code"] for o in offers]
            idf_codes = {s["seller_code"] for s in idf}
            hits = [c for c in codes if c in idf_codes]
            print(f"\n  API stock (sku {CULTURA_TEST_SKU}) renvoie {len(codes)} magasins :")
            for o in offers:
                tag = "IDF" if o["seller_code"] in idf_codes else "hors IDF"
                print(f"    {o['seller_code']:5s} [{tag:8s}] "
                      f"{o['front_availability']} qty~{o['qty']}")
            print(f"  => {len(hits)}/{len(codes)} en IDF "
                  f"(hypothese 'sous-ensemble = region de l'IP' "
                  f"{'PLUTOT CONFIRMEE' if codes and len(hits) >= len(codes) * 0.7 else 'NON confirmee'})")
        else:
            print(f"  test stock HTTP {res['status']} - {res['text'][:80]}")

    return idf


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    if which in ("kj", "kingjouet", "all"):
        _save_out("kingjouet", build_kingjouet())
    if which in ("fnac", "all"):
        _save_out("fnac", build_fnac())
    if which in ("cultura", "all"):
        _save_out("cultura", build_cultura())


if __name__ == "__main__":
    main()
