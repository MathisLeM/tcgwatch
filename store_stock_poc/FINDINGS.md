# Test de faisabilité — stock par magasin (Fnac / King Jouet / Cultura)

Testé le 14/07/2026, sur des boosters One Piece réels, en inspectant le trafic
réseau de chaque site (aucune modification du reste du projet TCG_Scrapper —
tout ce travail vit dans ce sous-dossier `store_stock_poc/`).

## Verdict global

Faisable pour les 3 enseignes, sans navigateur (juste des requêtes HTTP). Chacune
expose un mécanisme différent, mais dans les trois cas on obtient un statut de
stock réel par magasin sur un produit donné.

## Fnac

- `GET /api/reference/rest/v3/geocoding?term=<ville/CP>` → lat/lon
- `POST /nav/api/StorePickup/SearchStore` (form-urlencoded : `inputValue`,
  `latitude`, `longitude`, `prid`, `catalog`, `formId`, `offerref`...) → fragment
  HTML listant ~30 magasins triés par distance, avec statut texte "En rayon"
  (dispo) / "Indisponible", adresse et id magasin.
- Le `formId` n'est **pas vérifié côté serveur** (testé avec une valeur bidon :
  fonctionne quand même) — pas de token à récupérer dynamiquement.
- ~30 magasins par requête → il faudra balayer des codes postaux/départements
  pour couvrir tout le réseau (~700 magasins Fnac).

## King Jouet

- API REST/JSON propre, sans authentification :
  `GET /api/store/search/postal-code?query=<CP>` → 5 magasins proches (guid,
  nom, adresse, horaires).
  `GET /api/product/<uuid_produit>/availability-in-stores/<guid1>_..._<guidN>`
  → statut par magasin ("Non disponible" / "Retrait en 2h" / ...).
- L'UUID produit n'est pas dans l'URL (qui utilise une référence numérique) mais
  est embarqué dans le HTML de la page produit — extractible par regex.
- 5 magasins par requête → balayage nécessaire (~240 magasins King Jouet).

## Cultura

- Backend Magento **GraphQL** public (`POST /magento/graphql`), introspection
  activée (schéma explorable directement).
- **Bonne nouvelle** : l'annuaire complet des magasins s'obtient en **un seul
  appel** (`stores(limit:200, country_code:"FR")` → 118 magasins), contrairement
  aux deux autres enseignes.
- Le stock par magasin existe bien dans le schéma (`stock_item_extra.offer` →
  liste de `{seller_code, front_availability, qty}` par produit), et les valeurs
  observées sont cohérentes avec l'UI.
- **Point non résolu** : ce champ ne prend aucun paramètre, et le sous-ensemble
  de magasins renvoyé (9 dans nos tests) n'a pas bougé quand on a fait varier le
  code postal recherché, ni en changeant manuellement le cookie
  `preferred_shop`. Il semble fixé par la géolocalisation IP et/ou un cookie
  `oss-eresa-cultura` non encore décodé. Confirmé à nouveau lors du POC
  dashboard IDF (cf. `idf_dashboard_stock_apis.py`) : seul un sous-ensemble fixe
  de magasins renvoie un vrai statut, les autres magasins proches affichent
  "non vérifiable".
- Cultura est protégé par **DataDome** (cookie détecté) — à surveiller de près
  une fois qu'on passera en volume ; Fnac et King Jouet n'ont montré aucun signe
  de protection anti-bot équivalente pendant ce test.

## Prochaines étapes proposées

1. Percer le mécanisme de ciblage géographique de Cultura (session/cookie).
2. Construire la liste des magasins par enseigne pour toute la France :
   - Cultura : un seul appel suffit (118 magasins, déjà fait pour l'IDF —
     cf. `idf_dashboard_catalog.py` → `CULTURA_IDF_STORES`).
   - Fnac / King Jouet : balayage par département ou grille de codes postaux
     (dédoublonnage par id/guid magasin), comme anticipé.
3. Étendre le PoC en scraper planifié (fréquence raisonnable, cf. consigne
   "ce projet tourne contre des sites en production").

---

# POC dashboard Île-de-France (étape suivante, livrée dans ce même dossier)

`idf_dashboard_app.py` (+ `idf_dashboard_catalog.py` + `idf_dashboard_stock_apis.py`) :
dashboard Streamlit où l'utilisateur saisit un code postal/ville et voit, pour
chaque référence cataloguée, les magasins IDF les plus proches et leur statut
de stock (interrogé en direct, pas de base de données).

Catalogue couvert : boosters/double packs/blisters des sets **EB03, OP13,
OP14, OP15, OP16, PRB02**. Sur 18 combinaisons possibles (6 sets × 3
enseignes), 15 ont été trouvées — certaines références n'existent simplement
pas chez certaines enseignes (ex : PRB02 absent chez Fnac, OP13 absent chez
King Jouet). Détail exact des IDs par enseigne dans `idf_dashboard_catalog.py`.

Lancer avec :
```
pip install streamlit requests beautifulsoup4 lxml
streamlit run idf_dashboard_app.py
```

---

# ⚠️ Mise à jour 14/07/2026 (soir) — DataDome bloque désormais les 3 enseignes

En attaquant l'étape "annuaire des magasins IDF" (`build_idf_stores.py`), constat
qui **change le tableau par rapport aux notes ci-dessus** :

- Les endpoints validés plus haut (Fnac `SearchStore`, King Jouet
  `store/search`, Cultura GraphQL) renvoient tous **HTTP 403 + challenge
  DataDome** (`geo.captcha-delivery.com`) dès qu'on les appelle depuis autre
  chose qu'un vrai navigateur "propre".
- Testé et **tous bloqués** : `requests`, `curl_cffi` avec impersonation Chrome
  (TLS/JA3 réalistes) + warm-up de session, et **`scraper.stealth_browser`
  (Playwright) réglé pour Micromania/Incapsula** — headless *et* headful.
- Testé aussi depuis le **navigateur réel intégré** (vrai fingerprint Chrome) :
  challenge DataDome interactif (`t=fe`) là aussi.
- Les notes d'origine disaient "Fnac/King Jouet : aucun signe d'anti-bot". Deux
  lectures possibles, non tranchées : soit le POC initial a été relevé depuis le
  vrai navigateur de l'utilisateur (session/cookies humains) sans jamais frapper
  en HTTP pur ; soit DataDome a été durci depuis. **Le cookie `datadome` est
  maintenant posé par les trois sites**, pas seulement Cultura.
- Facteur aggravant probable : l'**IP de sortie de l'environnement de dev**
  (résidentielle, `81.220.111.5`) s'est fait **flaguer par DataDome** au fil de
  ces tests répétés → le challenge est passé en mode CAPTCHA interactif. À ne
  **pas** contourner (résoudre un CAPTCHA = hors périmètre).

## Conséquence sur l'architecture

Le point dur n'est plus "trouver les endpoints" (ils sont connus et corrects)
mais **passer DataDome de façon fiable et planifiée**, ce qui est un problème
d'un autre ordre :

1. **Le stealth_browser actuel (Incapsula/Micromania) ne suffit pas** pour
   DataDome. Il faudrait au minimum : un profil Chromium plus furtif
   (rebrowser/undetected patches), et surtout des **proxys résidentiels
   tournants** — DataDome bloque à l'IP, donc une IP fixe de scan planifié se
   fera bannir vite. C'est la même famille de protection que celle qui a fait
   classer ces enseignes `blocked` dans `api/retailers.py` (registre qui, du
   coup, avait raison — ma remarque précédente le disant "périmé" est à
   annuler).
2. **King Jouet** ajoute Cloudflare **par-dessus** DataDome (noté dans le
   registre) → double barrière.
3. **Ordre de difficulté anti-bot** : Cultura ≈ Fnac < King Jouet, mais les
   trois nécessitent la même brique "navigateur furtif + proxys résidentiels".

## Reco révisée

- **Ne pas** bâtir le scan planifié sur l'approche HTTP-pur/stealth actuelle :
  il tiendra quelques requêtes puis se fera bannir à l'IP.
- Décision produit à prendre avant d'investir : soit (a) budget **proxys
  résidentiels + navigateur anti-DataDome** (coût récurrent, maintenance
  continue, fragile), soit (b) rester sur le **live à la demande déclenché par
  une action utilisateur** (volume faible, moins suspect, mais ne remplit pas
  l'objectif "scan global en une fois"), soit (c) repli sur les enseignes **sans
  DataDome** pour le scan de fond et ne garder Fnac/KJ/Cultura qu'en
  vérification ponctuelle.
- `build_idf_stores.py` est **conservé** : le code (balayage + parsing +
  fusion + test hypothèse géo Cultura) est correct et prêt à tourner le jour où
  la brique anti-bot est en place ; aujourd'hui il ne renvoie que des 403.
- **Hypothèse géo Cultura : non tranchée** ce coup-ci (bloqué avant de pouvoir
  la tester). Reste le point ouvert des notes d'origine.
