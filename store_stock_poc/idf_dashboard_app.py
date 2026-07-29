"""
Dashboard POC (Streamlit) - stock magasin Île-de-France pour boosters One
Piece ciblés (EB03, OP13, OP14, OP15, OP16, PRB02).

Isole du reste du projet TCG_Scrapper (tout vit dans ce sous-dossier
store_stock_poc/). A lancer avec :

    pip install streamlit requests beautifulsoup4 lxml
    streamlit run idf_dashboard_app.py

L'utilisateur final saisit un code postal ou une ville ; le dashboard
interroge en direct Fnac, King Jouet et Cultura (aucune base de donnees, tout
est en live) et affiche, pour chaque produit du catalogue, les magasins
d'Île-de-France les plus proches avec leur statut de stock.
"""

import streamlit as st

from idf_dashboard_catalog import PRODUCTS
from idf_dashboard_stock_apis import (
    cultura_idf_stock,
    fnac_idf_stock,
    geocode,
    kingjouet_idf_stock,
)

st.set_page_config(page_title="Stock One Piece - Île-de-France", layout="wide")

st.title("📍 Stock boosters One Piece — Île-de-France")
st.caption(
    "POC : Fnac, King Jouet, Cultura. Sets couverts : EB03, OP13, OP14, OP15, "
    "OP16, PRB02 (booster / double pack / blister). Recherche en direct sur "
    "les sites — aucune base de données, les résultats reflètent le stock au "
    "moment de la recherche."
)

with st.form("search_form"):
    col1, col2 = st.columns([3, 1])
    with col1:
        user_input = st.text_input(
            "Votre code postal ou votre ville",
            placeholder="ex : 75001, Paris, Versailles...",
        )
    with col2:
        set_filter = st.selectbox(
            "Set (optionnel)", ["Tous"] + sorted({p["set_code"] for p in PRODUCTS})
        )
    submitted = st.form_submit_button("Rechercher", use_container_width=True)

if submitted:
    if not user_input.strip():
        st.error("Merci de saisir un code postal ou une ville.")
        st.stop()

    try:
        user_lat, user_lon = geocode(user_input)
    except Exception as e:
        st.error(f"Impossible de localiser « {user_input} » : {e}")
        st.stop()

    st.success(f"Localisation trouvée : {user_input} ({user_lat:.4f}, {user_lon:.4f})")

    products = [p for p in PRODUCTS if set_filter == "Tous" or p["set_code"] == set_filter]

    for product in products:
        st.subheader(f'{product["set_code"]} — {product["variant"]}')
        st.caption(product["name"])

        with st.spinner("Recherche des magasins à proximité..."):
            rows = []

            fnac_prid = product["fnac"].get("prid")
            if fnac_prid:
                try:
                    for s in fnac_idf_stock(fnac_prid, user_input):
                        rows.append(
                            {
                                "Enseigne": s.retailer,
                                "Magasin": s.store_name,
                                "Ville": s.city,
                                "Code postal": s.postcode,
                                "Statut": s.raw_status,
                                "Disponible": "✅" if s.available else "❌",
                            }
                        )
                except Exception as e:
                    st.caption(f"Fnac : erreur ({e})")

            kj_uuid = product["kingjouet"].get("uuid")
            if kj_uuid:
                try:
                    for s in kingjouet_idf_stock(kj_uuid, user_input):
                        rows.append(
                            {
                                "Enseigne": s.retailer,
                                "Magasin": s.store_name,
                                "Ville": s.city,
                                "Code postal": s.postcode,
                                "Statut": s.raw_status,
                                "Disponible": "✅" if s.available else "❌",
                            }
                        )
                except Exception as e:
                    st.caption(f"King Jouet : erreur ({e})")

            cultura_sku = product["cultura"].get("sku")
            if cultura_sku:
                try:
                    for s in cultura_idf_stock(cultura_sku, user_lat, user_lon):
                        rows.append(
                            {
                                "Enseigne": s.retailer,
                                "Magasin": s.store_name,
                                "Ville": s.city,
                                "Code postal": s.postcode,
                                "Statut": s.raw_status,
                                "Disponible": "✅" if s.available else "❌",
                                "Distance (km)": s.distance_km,
                            }
                        )
                except Exception as e:
                    st.caption(f"Cultura : erreur ({e})")

        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Aucun magasin trouvé pour ce produit chez les enseignes disponibles.")

        st.divider()

else:
    st.info("Renseignez un code postal ou une ville puis cliquez sur Rechercher.")

st.markdown("---")
st.caption(
    "⚠️ Limitation connue : pour Cultura, l'API de stock ne cible pas "
    "précisément la zone demandée (elle renvoie un ensemble de magasins fixé "
    "côté serveur). Les magasins Cultura affichés sont donc toujours les plus "
    "proches d'après notre annuaire Île-de-France, mais le statut de stock "
    "n'est renseigné que si l'API renvoie une réponse pour ce magasin — sinon "
    "il apparaît comme « non vérifiable »."
)
