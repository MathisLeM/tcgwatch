# Architecture

## Vue d'ensemble

```
                       POSTE LOCAL (Windows)                                   PROD
 ┌──────────────────────────────────────────────────────────┐
 │ Boutiques en ligne (Shopify, Woo, PrestaShop, …)          │
 │        │  discover_<plateforme>  (1 fois / boutique)      │
 │        ▼                                                  │
 │  products  ◄── curation Excel / new_products / add_site   │
 │        │  fetch_<plateforme>  via scraper.run (routine)   │
 │        ▼                                                  │
 │  snapshots (prix, stock)        data/tcg_stock.sqlite ────┼── scripts.sync_to_prod ──►  Supabase Postgres
 │                                   ▲                       │                                 │
 │ TCGdex / Pokecardex ── sets, catalog (référentiel)        │                                 ▼
 │ Cardmarket price_guide ── cm_tracked, cm_prices           │                       API FastAPI (Railway)
 └──────────────────────────────────────────────────────────┘                                 │
                                                                                              ▼
                                                                                   Frontend Next.js (Vercel)
```

- La **SQLite locale** (`data/tcg_stock.sqlite`) est la source de vérité des
  données scrapées. Elle n'est pas versionnée : sauvegarde-la.
- La **prod** (Supabase) est un miroir alimenté à la main par `scripts.sync_to_prod`.
  Les tables applicatives (`users`, `favorites`, `alert_*`, `waitlist_signups`)
  n'existent de façon significative qu'en prod et ne sont jamais écrasées par la sync.
- L'**API** lit la base désignée par `DATABASE_URL` : SQLite en local, Supabase en prod.

## État du déploiement (alpha)

| Brique | État |
|---|---|
| Frontend Vercel — https://tcgwatch.vercel.app | ✅ en ligne |
| API Railway — https://tcgwatch-production.up.railway.app | ✅ en ligne (`/health`) |
| Supabase Postgres | ✅ — **free tier : pause après ~7 j sans trafic**. Symptôme : `/health` = 200 mais les endpoints DB renvoient 500 → réveiller le projet dans la console Supabase |
| Worker scraper (`railway.worker.toml`) | ❌ non déployé — la prod ne se rafraîchit pas seule |
| Cloudflare R2 | ❌ non branché — images servies par l'API (`/images`) |
| Domaine / facturation | ❌ |

Inscriptions publiques fermées (`ALLOW_PUBLIC_SIGNUP=false`) ; `/docs` et
`/openapi.json` sont désactivés en prod.

## Le scraper (`scraper/`)

Deux étapes par plateforme, **indépendantes du jeu** :

| Étape | Modules | Fréquence | Rôle |
|---|---|---|---|
| Découverte | `discover_<plateforme>.py` | ponctuelle | Lister les produits scellés d'une boutique → Excel à curer |
| Relevé | `fetch_<plateforme>.py` via `run.py` | routine | Pour chaque produit connu, relire prix + stock → `snapshots` |

Plateformes : Shopify (`/products/<h>.json`), WooCommerce (Store API), PrestaShop
(microdata schema.org), Wix (GraphQL storefront), Powerboutique, Next.js (PlayIn,
Parkage), e-monsite (JSON-LD), FantasySphere (listing), Micromania (navigateur
furtif Playwright, Pokémon uniquement — derrière Imperva).

Logique par jeu dans `scraper/games/` : `optcg.py` (OPTCG + Naruto, **FR uniquement**,
s'appuie sur `cleanup.py`) et `pokemon.py` (**FR/EN/JA/KO/ZH**, détection langue,
set, type de produit). Le registre `games/__init__.py` expose `get_game(name)`.

Les boutiques ajoutées après coup sont déclarées dans `data/extra_shops.json`
(lu par `shop_registry.py`), pas dans le code.

`scraper/db.py` est la couche SQL brute du scraper : **SQLite par défaut, Postgres
si `DATABASE_URL` pointe ailleurs**. ⚠️ Un `.env` resté sur Supabase fait donc
écrire `scraper.run` directement en prod.

Modules annexes :
- `cardmarket/` — cotes marché Cardmarket (OPTCG), tables isolées `cm_tracked` / `cm_prices`.
- `valuation/` — modèle de sur/sous-valorisation des cartes OPTCG (Limitless, régression).
- `alerting.py` — détection restock / baisse de prix + envoi e-mail / Discord.
- `worker.py` — boucle planifiée (APScheduler) scrape + alertes, prévue pour Railway.
- `legacy/` — scripts one-shot conservés pour référence.

## L'API (`api/`, `main.py`)

FastAPI, structure calquée sur Vigilyx : `config.py` (pydantic-settings),
`database.py` (SQLAlchemy ; `create_all` en dev, `alembic upgrade head` au boot en
prod), `models/`, `routers/`, `services/`.

| Préfixe | Endpoints principaux |
|---|---|
| `/auth` | `POST /signup` (fermé en alpha), `POST /login`, `POST /logout`, `GET /me` |
| `/products` | `GET /` (paginé, filtres), `GET /history` (sparklines 30 j, batch), `GET /facets` |
| `/sets` | `GET /`, `GET /blocks` (arbre bloc > set > type Pokémon) |
| `/catalog` | `GET /games`, `GET /`, `GET /listings` |
| `/trends` | `GET /`, `GET /{id_product}` — cotes Cardmarket |
| `/retailers` | grandes enseignes — **aucune `live`**, endpoints produits/magasins en 409 |
| `/favorites`, `/alerts` | watchlist et règles d'alerte de l'utilisateur |
| `/waitlist` | `POST /` public (rate limit 5/min/IP), `GET /` et `/stats` admin |
| `/health`, `/images` | santé, fichiers statiques de `images/` |

## Modèle de données

| Table | Couche | Contenu |
|---|---|---|
| `sites` | scraper + API | boutiques suivies (host, plateforme, jeux) |
| `sets` | scraper + API | référentiel de sets par `(game, language, set_code)` (TCGdex) |
| `catalog` | scraper + API | SKU canonique `(game, language, set_code, kind)` |
| `products` | scraper + API | annonce d'une boutique ; identité stable `(platform, shop, platform_pid)` |
| `snapshots` | scraper + API | historique prix/stock, une ligne par relevé et par produit |
| `cm_tracked`, `cm_prices` | Cardmarket | produits suivis + série de cotes par jour |
| `users`, `favorites`, `alert_configs`, `alert_events` | API seule | comptes, watchlist, règles, journal anti-doublon |
| `waitlist_signups` | API seule | e-mails de la liste d'attente |

Les tables cœur existent deux fois — SQL brut dans `scraper/db.py` et ORM dans
`api/models/catalog.py` — et doivent rester **compatibles colonne pour colonne**.
Toute modification de `api/models/` s'accompagne d'une migration Alembic
(`migrations/versions/`).

## Frontend (`frontend/`)

Next.js 16 (App Router) / React 19 / Tailwind v4, en français. Pages : landing
(`/`), `/login`, `/dashboard`, `/catalog`, `/trends`, `/favorites`, `/alerts`.
Tous les appels passent par `lib/api.ts`. Conventions détaillées dans
[frontend/CLAUDE.md](../frontend/CLAUDE.md).
