# Référence des scripts

Légende du type : 🔁 routine · 🛠️ ponctuel / maintenance · 📚 référentiel · 🧩 module
(importé, pas lancé directement) · 🗄️ legacy (historique, ne pas relancer sans savoir
pourquoi).

Toutes les commandes se lancent depuis la racine, en `python -m <module>`. La
colonne « DB » précise si le script écrit en base, en suivant `DATABASE_URL`
(SQLite locale par défaut).

## Points d'entrée

| Fichier | Type | Commande | Rôle |
|---|---|---|---|
| `main.py` | 🔁 | `uvicorn main:app --reload` | API FastAPI : CORS, rate limit, `/health`, montage `/images`, refuse de démarrer en prod si `SECRET_KEY` est un placeholder |
| `app.py` | 🗄️ | `streamlit run app.py` | Ancien dashboard Streamlit (local, lecture SQLite) |
| `scraper/worker.py` | 🔁 | `python -m scraper.worker` | Boucle APScheduler : scrape toutes les `SCRAPE_INTERVAL_HOURS` h (`SCRAPE_GAMES`) puis alertes. Prévu pour Railway, **non déployé** |

## Scraper : orchestration

| Module | Type | Commande / arguments | Entrées → Sorties |
|---|---|---|---|
| `scraper.run` | 🔁 | `--game optcg\|pokemon\|all` (déf. `all`), `--no-fetch` / `--report-only` (rapport seul) | Lance les 9 `fetch_*`, écrit `snapshots`, affiche restocks / ruptures / prix + durée par plateforme |
| `scraper.export_excel` | 🔁 | (aucun) | DB → `data/products_view.xlsx` (onglets ALL, AVAILABLE NOW, CHANGES, CHEAPEST PER SET, SUMMARY) |
| `scraper.alerting` | 🔁 | `python -m scraper.alerting` | Compare les 2 derniers snapshots, crée les événements `restock` / `price_drop`, notifie via e-mail / Discord, dédoublonne via `alert_events` |
| `scraper.db` | 🧩 | `python -m scraper.db` = init schéma SQLite | Couche SQL brute (SQLite ou Postgres selon `DATABASE_URL`) |
| `scraper.config` | 🧩 | — | Chemins (`DATA_DIR`, `DB_PATH`, `IMAGES_DIR`), user-agent, timeout, délai par domaine |
| `scraper.timing` | 🧩 | — | Chronométrage et tableau récapitulatif des durées |
| `scraper.shop_registry` | 🧩 | — | Fusionne les boutiques codées en dur avec `data/extra_shops.json` |
| `scraper.cleanup` | 🧩 | — | Filtres OPTCG/Naruto : éditions étrangères, extraction du code de set, exclusions (figurines, tins…) |
| `scraper.stealth_browser` | 🧩 | — | Context manager Chromium headless furtif (Playwright + playwright-stealth) pour les sites Imperva |
| `scraper.micromania_parse` | 🧩 | — | Parsing HTML Micromania hors réseau (testé sur fixtures) |

## Scraper : plateformes

Chaque plateforme a un `discover_*` (🛠️, lancé à la main, écrit
`data/discovered_<plateforme>.xlsx` à curer) et un `fetch_*` (🧩, appelé par
`scraper.run`). Les `discover_*` n'ont pas d'arguments, sauf Micromania.

| Plateforme | Accès aux données | Boutiques (local) |
|---|---|---|
| Shopify | `/collections.json` puis `/products/<handle>.json` | 37 |
| WooCommerce | Store API `/wp-json/wc/store/products`, repli HTML | 34 |
| PrestaShop | recherche (standard / ambjolisearch / iqitsearch) + microdata schema.org | 28 |
| Wix | jeton d'instance + GraphQL storefront | 2 |
| Powerboutique | pages catégorie `?numPage=N` + microdata | 2 |
| Next.js | Parkage : API Strapi · PlayIn : sitemap + JSON-LD | 1 |
| e-monsite | sitemap + JSON-LD | 1 |
| FantasySphere | tuiles des pages catégorie | 1 |
| Micromania | Chromium furtif, Pokémon uniquement | 1 |

`python -m scraper.discover_micromania [--limit N] [--dry-run] [--no-details] [--headful]`
écrit **directement en base** (sauf `--dry-run`).

## Scraper : curation des produits

| Module | Type | Commande / arguments | Rôle |
|---|---|---|---|
| `scraper.new_products` | 🔁 | `generate` puis `apply` | Diff découverte vs `products` + `ignored_products.json` → `data/new_products.xlsx` (KEEP/DROP) → applique |
| `scraper.add_site` | 🛠️ | interactif, ou `--url --name [--optcg-url] [--naruto-url]` | Onboarding d'une boutique Shopify, PrestaShop ou WooCommerce (voir workflows §3) |
| `scraper.load_curated` | 🛠️ | (aucun) | Charge les `data/discovered_<plateforme>.xlsx` curés dans `products` (upsert) |
| `scraper.discover_pokemon` | 🛠️ | (aucun) | Extraction Pokémon brute de toutes les boutiques → `data/discovered_pokemon_raw.xlsx` |
| `scraper.categorize_pokemon` | 🛠️ | (aucun) | Filtre le scellé, catégorise (langue, set, type), écrit `discovered_pokemon.xlsx` **et charge en base**. ⚠️ Supprime puis recharge les produits Pokémon (hors Micromania) : l'historique de snapshots part en cascade |
| `scraper.upload_images` | 🛠️ | `[--dry-run] [--force] [--prefix P]` | Envoie `images/` vers Cloudflare R2 (dry-run automatique si R2 n'est pas configuré). En attente de R2 |

## Scraper : référentiel par jeu (`scraper/games/`)

| Module | Type | Commande / arguments | Rôle |
|---|---|---|---|
| `games.optcg` / `games.pokemon` / `games.base` | 🧩 | — | Logique par jeu : détection langue, code de set, type de produit, exclusion des autres TCG |
| `games.build_pokemon_sets` | 📚 | (aucun) | TCGdex → `data/reference/pokemon_sets.json` + table `sets` (sorties ≥ 2020) |
| `games.build_pokemon_dictionary` | 📚 | (aucun) | Noms de séries et de sets en 5 langues → `pokemon_series.json`, `pokemon_set_dictionary.xlsx` |
| `games.cardmarket` | 📚 | (aucun) | Dump Cardmarket non-singles → types de produits existants par set |
| `games.pokemon_catalog` | 📚 | `export` \| `load` | Aller-retour avec `data/pokemon_catalog.xlsx` ↔ table `catalog` |
| `games.pokemon_hierarchy` | 📚 | `[--language fr ...]` (répétable) | Arbre bloc > set > type → `pokemon_hierarchy.json` / `.xlsx` (même code que `GET /sets/blocks`) |
| `games.build_pokecardex` | 📚 | `[--limit N] [--force] [--dry-run]` | Sitemap Pokecardex → `data/reference/pokecardex_sets.json` (noms FR + URL des logos) |
| `scraper.fetch_set_images` | 📚 | `[--limit N] [--dry-run]` | Logos manquants depuis le CDN TCGdex → `images/Pokemon/Image_Serie_auto/` |
| `scraper.fetch_pokecardex_images` | 📚 | `[--limit N] [--force] [--dry-run]` | Logos Pokecardex → `images/Pokemon/Image_Serie_pokecardex/` |

## Cotes Cardmarket (`scraper/cardmarket/`)

| Module | Type | Commande / arguments | Rôle |
|---|---|---|---|
| `cardmarket.track` | 🛠️ | `seed` · `add-single <url>` · `add-sealed <idProduct> <code> <kind> <nom…>` · `list` | Gère `cm_tracked` (graines : `data/cardmarket/tracked_*.json`) |
| `cardmarket.ingest` | 🔁 | `[fichier]` (déf. tous les `price_guide_*.json`) | Upsert `cm_prices` par `(id_product, jour)`, idempotent |
| `cardmarket.resolver` | 🧩 | — | URL Cardmarket d'une carte → `idProduct`, via les catalogues locaux (sans scraping) |

## Valorisation OPTCG (`scraper/valuation/`)

| Module | Type | Commande / arguments | Rôle |
|---|---|---|---|
| `valuation.cards_limitless` | 📚 | `<SETS…> [--refresh]` | Limitless → `data/valuation/optcg_cards_limitless.json` (rareté, versions, prix EUR) |
| `valuation.playability` | 📚 | `[--format OP16] [--refresh]` | Méta Limitless → `data/valuation/playability.json` (score 0-3) |
| `valuation.rank` | 🛠️ | `[SETS…] [--all] [--top 12] [--min-price 5] [--cv K]` | Régression OLS `ln(prix)` ; le résidu donne le signal sur/sous-valorisé |
| `valuation.analysis` | 🛠️ | `[SETS…] [--pack 4.0]` | Analyse exploratoire → PNG dans `data/valuation/analysis/` |
| `valuation.odds` / `popularity` / `model` | 🧩 | — | Taux de drop, popularité WT100, modèle de référence à poids manuels |

## Scripts d'admin (`scripts/`)

| Module | Type | Commande / arguments | Rôle |
|---|---|---|---|
| `scripts.sync_to_prod` | 🔁 | `[--dry-run] [--full] [--only t1,t2] [--migrate] [--source …] [--target URL] [--force-sqlite]` | Upsert SQLite locale → cible (`--target` ou `DATABASE_URL`). Référentiel intégral, séries temporelles incrémentales (`--full` = tout). Ne touche jamais aux tables applicatives |
| `scripts.manage_users` | 🛠️ | `create <id> [--password] [--admin]` · `list` · `passwd <id>` · `activate` · `deactivate` · `delete` | Comptes alpha (hash bcrypt identique à l'API) |

## Legacy (`scraper/legacy/`, `scripts/legacy/`)

Conservés pour la traçabilité. Ils ont déjà fait leur travail.

| Module | Ancien rôle | Remarque |
|---|---|---|
| `scraper.legacy.migrate_from_optcg` | Import initial de l'ancienne base OPTCG_Scrapper (**DELETE puis remplacement**) | `--src`, `--force` |
| `scraper.legacy.recategorize_optcg` | Passe unique de suppression des éditions OPTCG non françaises | dry-run par défaut, `--apply` ; audit dans `data/recategorize_optcg_dropped.csv` |
| `scraper.legacy.apitcg_rarity` | Ancienne source de rareté (miroir apitcg) | Remplacée par `cards_limitless` ; ses helpers purs restent testés |
| `scraper.legacy.poc.micromania_playwright` | POC de faisabilité Imperva | A donné `stealth_browser.py` ; captures dans `TCG_Scrapper_archive` |
| `scripts.legacy.migrate_sqlite_to_postgres` | Copie initiale SQLite → Supabase (INSERT bruts, **non rejouable**) | Utiliser `sync_to_prod` |
| `scripts.legacy.merge_optcg_history` | Fusion non destructive de l'historique OPTCG (avec backup) | `--src`, `--dry-run` |
| `scripts.legacy.build_promo_packs` | Liste promo packs OPTCG → cartes (Limitless + Cardmarket) | Nécessite `data/OP26062026/` (archivé). S'exécute dès l'import |
| `scripts.legacy.fetch_promo_pack_images` | Images des promo packs via tcgcsv / TCGplayer | `--no-download` |

## POC magasins (`store_stock_poc/`)

Dossier isolé, non branché à l'application (voir `store_stock_poc/FINDINGS.md`).

| Fichier | Commande | Rôle |
|---|---|---|
| `poc_store_stock.py` | `python store_stock_poc/poc_store_stock.py [code_postal]` | Test de stock en magasin Fnac, King Jouet et Cultura (`requests`) |
| `build_idf_stores.py` | `python store_stock_poc/build_idf_stores.py [kj\|fnac\|cultura\|all]` | Annuaire des magasins d'Île-de-France (Playwright, contourne DataDome) |
| `idf_dashboard_app.py` | `streamlit run store_stock_poc/idf_dashboard_app.py` | Dashboard du stock en magasin en Île-de-France |

## Raccourcis Windows (`launch_*.bat`)

| Fichier | Lance |
|---|---|
| `launch_app.bat` | API (`uvicorn --reload`, SQLite forcée) dans une fenêtre + frontend `npm run dev`, ouvre le navigateur |
| `launch_landing.bat` | Frontend seul (`npm install` au premier lancement) |
| `launch_scraping_optcg.bat` | `scraper.run --game optcg` puis `scraper.export_excel` |
| `launch_scraping_pokemon.bat` | `scraper.run --game pokemon` puis `scraper.export_excel` |
| `launch_new_products.bat` | `new_products generate`, pause pour éditer l'Excel, puis `apply` |
| `launch_add_site.bat` | `scraper.add_site` (interactif) |
| `launch_sync_prod.bat` | `sync_to_prod --dry-run`, confirmation O/N, puis push |
| `launch_dashboard.bat` | `streamlit run app.py` (legacy) |
