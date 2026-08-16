# TCG_Scrapper (TCGWatch)

Tracks stock/price of **sealed TCG products** across many French online shops.
Multi-game: **OPTCG / Naruto Mythos** (French only) and **Pokemon TCG**
(multi-language: FR / EN / JA / KO / ZH). Started as a Streamlit scraper, has
since grown into a full monorepo product ("TCGWatch") built on the same stack
as the sibling project **Vigilyx** (`C:\Users\mathi\vigilyx`): **Next.js**
(frontend) · **FastAPI** (API + worker) · **SQLAlchemy/Postgres-compatible DB**
· S3-compatible image storage.

The scraper (9 platform fetchers, game-agnostic) is the original core and still
runs standalone; `api/` + `frontend/` are the newer product layer built on top
of the same local SQLite data. `app.py` (Streamlit) is the legacy local-only
dashboard, superseded by `frontend/` but kept for quick local inspection.

## Deployment status (à jour au 2026-08-17)

**L'alpha est déployée**, selon le plan `DEPLOYMENT_ALPHA.md` (pas `DEPLOYMENT.md`,
qui reste la cible complète à atteindre) :

| Brique | État |
|---|---|
| Frontend Vercel — https://tcgwatch.vercel.app | ✅ en ligne (landing v2 + pages app) |
| API Railway — https://tcgwatch-production.up.railway.app | ✅ en ligne (`/health`) |
| DB Supabase Postgres | ✅ en ligne — **free tier : se met en pause après ~7 j d'inactivité**. Symptôme : `/health` répond 200 mais tous les endpoints DB renvoient 500. Réveiller le projet dans la console Supabase. |
| Worker scraper (`railway.worker.toml`) | ❌ pas de service Railway — **la prod ne se rafraîchit pas toute seule** |
| Cloudflare R2 | ❌ non branché — les images sont servies par Railway (`/images`) |
| Domaine propre / facturation | ❌ inexistants (les formules de la landing sont décoratives) |

Conséquences pratiques :
- **La prod est un miroir en lecture seule du SQLite local.** On scrape en local,
  puis on pousse avec `python -m scripts.sync_to_prod` (rejouable, cf. Run).
- Inscriptions publiques fermées (`ALLOW_PUBLIC_SIGNUP=false`) : les comptes se
  créent à la main via `python -m scripts.manage_users create`.
- `/docs`, `/redoc` et `/openapi.json` sont désactivés en prod (`ENVIRONMENT=production`).
- Le formulaire de liste d'attente de la landing est en `action="#"` — **aucun
  e-mail n'est collecté** pour l'instant.
- Le repo GitHub (`MathisLeM/tcgwatch`) est **public** (aucun secret commité).

Le dev local reste 100 % SQLite (`data/tcg_stock.sqlite`) + `uvicorn --reload` /
`npm run dev` — aucune variable d'environnement requise.

## Run
- API (dev, reads local SQLite): `uvicorn main:app --reload` → http://127.0.0.1:8000/docs
- Frontend (dev): `cd frontend && npm run dev` → http://localhost:3000
- Scraper worker (prod-like loop): `python -m scraper.worker`
- Snapshot OPTCG:   `python -m scraper.run --game optcg`   (or `launch_scraping_optcg.bat`)
- Snapshot Pokemon: `python -m scraper.run --game pokemon` (or `launch_scraping_pokemon.bat`)
- Snapshot all:     `python -m scraper.run` (default `--game all`)
- Alerting only:    `python -c "from scraper.alerting import run_alerting; run_alerting()"`
- Rebuild Pokemon set reference: `python -m scraper.games.build_pokemon_sets`
- Build Pokemon navigation tree (block > set > type): `python -m scraper.games.pokemon_hierarchy`
- Fill missing set images (TCGdex CDN): `python -m scraper.fetch_set_images`
- Cardmarket price trends (OPTCG): seed `python -m scraper.cardmarket.track seed`,
  ingest `python -m scraper.cardmarket.ingest`, add a single
  `python -m scraper.cardmarket.track add-single <cardmarket-url>` (all honour `DATABASE_URL`).
- Card valuation (OPTCG over/under-valued): build the card source
  `python -m scraper.valuation.cards_limitless OP15 OP16 EB03`, refresh the meta
  `python -m scraper.valuation.playability`, then rank
  `python -m scraper.valuation.rank --all` (all keyless, HTML cached under `data/valuation/`).
- Legacy Streamlit dashboard: `streamlit run app.py` (or `launch_dashboard.bat`)
- Migrate old OPTCG DB: `python -m scraper.migrate_from_optcg`
- **Pousser les données locales en prod** (rejouable, `DATABASE_URL` = Supabase) :
  `python -m scripts.sync_to_prod --dry-run` puis `python -m scripts.sync_to_prod`
  (ou `launch_sync_prod.bat`, qui enchaîne les deux avec confirmation). Upsert :
  `sites`/`sets`/`catalog`/`products`/`cm_tracked` sont mis à jour intégralement,
  `snapshots`/`cm_prices` sont incrémentales (seules les lignes au-dessus du
  max(id) cible partent ; `--full` renvoie tout). Les tables applicatives
  (`users`, `favorites`, `alert_*`) ne sont jamais touchées.
- Migration initiale SQLite → Postgres (one-shot historique, non rejouable —
  utiliser `sync_to_prod` à la place) : `python -m scripts.migrate_sqlite_to_postgres`
- Tests: `pytest`

## Layout
- `scraper/`        — `run.py` orchestrates (`--game` filters by TCG); `fetch_<platform>.py`
  + `discover_<platform>.py` per platform (shopify, woocommerce, wix, powerboutique,
  nextjs, emonsite, fantasysphere, prestashop, micromania — game-agnostic);
  `db.py` = raw SQLite layer (legacy, still used by standalone scraper scripts);
  `worker.py` = Railway worker entrypoint (scheduled scrape + alert loop);
  `alerting.py` = restock/price-drop detection + dispatch; `cleanup.py`,
  `categorize_pokemon.py`, `recategorize_optcg.py`, `new_products.py` = maintenance
  scripts; `stealth_browser.py` + `poc/` = Playwright-based fetching for
  anti-bot-protected shops (Micromania).
- `scraper/games/`  — per-game logic: `optcg.py`, `pokemon.py`, registry in `__init__.py`,
  shared helpers in `base.py`; `build_pokemon_sets.py` / `build_pokemon_dictionary.py`
  pull TCGdex reference data; `cardmarket.py` derives which product kinds exist per
  set from the Cardmarket dump; `build_pokecardex.py` scrapes Pokecardex for images;
  `pokemon_catalog.py` round-trips the hand-editable catalog Excel (export/load);
  `pokemon_hierarchy.py` builds the **block > set > article-type** navigation tree
  (nested JSON + flat Excel) from the set reference + live product counts — the same
  `build_hierarchy()` backs the `/sets/blocks` API endpoint so site and export agree.
- `api/`            — FastAPI backend (mirrors Vigilyx's `app/`): `config.py` (pydantic-settings,
  see `.env.example`), `database.py` (SQLAlchemy engine/session, `create_all` in dev,
  Alembic in prod), `models/` (ORM — `catalog.py` mirrors the scraper's raw schema
  column-for-column so both layers read/write the same tables; `user.py`, `favorite.py`,
  `alert.py` are API-only, new tables), `routers/` (`auth`, `products`, `sets`,
  `retailers`, `favorites`, `alerts`), `services/` (`email_service.py`, `discord_service.py`,
  `notify.py` = channel dispatch, `r2.py` = image upload, `listings.py`, `store_inventory.py`,
  `images.py` = vignette par (game, set, kind) réutilisant l'art du catalogue,
  `kinds.py` = kind effectif + libellé lisible),
  `retailers.py` = curated registry of big retail chains (live/soon/blocked, for the
  "grandes enseignes" UI overlay — separate from the scraped `sites` table).
  **Aucune enseigne n'est `live` aujourd'hui** : Micromania est repassée en `soon`
  (POC stealth-browser + stock magasin pas assez fiables), le chantier "grandes
  enseignes" est en pause. Les endpoints `/retailers/{id}/products` et `/stores`
  répondent donc 409 ; leur code reste couvert par un test qui promeut
  temporairement Micromania en `live`.
- `frontend/`       — Next.js 16 / React 19 / TypeScript app (see `frontend/CLAUDE.md`;
  update that file too when frontend conventions change — it currently says the
  backend isn't built, which is now stale).
- `migrations/`     — Alembic migrations, run automatically at API startup in prod.
- `scripts/`        — `sync_to_prod.py` (push local → prod, rejouable) et
  `manage_users.py` (création de comptes alpha) sont les deux outils de routine ;
  one-off : `migrate_sqlite_to_postgres.py`, `build_promo_packs.py`,
  `fetch_promo_pack_images.py`, `merge_optcg_history.py`.
- `tests/`          — pytest for the API (`test_api.py`, `test_retailers.py`) and
  scraper logic (`test_pokemon_categorize.py`, `test_cleanup_language.py`,
  `test_micromania.py`).
- `data/`           — `tcg_stock.sqlite` (dev DB, also the source read by `api/` locally);
  `pokemon_catalog.xlsx` (hand-editable SKU list); `reference/` (TCGdex sets/series
  cache, Cardmarket + TCGplayer dumps, Pokecardex images cache).
- `images/`         — product thumbnails (served from Cloudflare R2 in prod).
- `main.py`         — FastAPI entrypoint (`uvicorn main:app`); `DEPLOYMENT.md` and
  `README.md` cover the Railway/Vercel/Supabase/R2 deploy in detail.

## Pokemon catalog workflow
1. `python -m scraper.games.build_pokemon_sets`         — refresh set reference (TCGdex).
1b.`python -m scraper.games.build_pokemon_dictionary`   — series names + multilingual
   set dictionary (`data/reference/pokemon_set_dictionary.xlsx`, `pokemon_series.json`).
2. `python -m scraper.games.cardmarket`                 — report product types per set.
3. `python -m scraper.games.pokemon_catalog export`     — write `data/pokemon_catalog.xlsx`
   (en/fr kinds pre-filled from Cardmarket; ja/ko/zh from a card_count baseline; TCG
   Pocket excluded). Edit the kind columns by hand (x = track).
4. `python -m scraper.games.pokemon_catalog load`       — upsert the `catalog` table.
5. `python -m scraper.fetch_set_images`                 — fill missing set logos (TCGdex CDN).
6. `python -m scraper.games.pokemon_hierarchy`          — build the block > set > type tree
   (`data/reference/pokemon_hierarchy.{json,xlsx}`) from the reference + scraped products.

Discovery → categorization (`scraper.discover_pokemon` then `scraper.categorize_pokemon`)
drops cross-game contamination (Lorcana / Yu-Gi-Oh / Weiss Schwarz / Dragon Ball / …
cross-listed in a shop's "Pokemon" collection) via `pokemon.is_other_tcg`, and stores
the canonical **block id** (JP era ids `SV`/`S`/`M` → `sv`/`swsh`/`me`) in `products.series`
so blocks group consistently across languages. Browse the result via `GET /sets/blocks`.

## Dashboard trend sparklines
`GET /products/history?product_id=…&days=30` returns a **batched** price series per
product, read from `snapshots` (indexed on `(product_id, observed_at)`) and reduced to
one point per day — the last observation of that day, since a day can hold several
scrape runs. Requested products with no priced snapshot in the window come back as an
empty list, never absent. The dashboard asks for every row of the current page in one
call. Distinct from `GET /trends`, which is Cardmarket market value keyed by
`id_product` — this one is *shop* prices keyed by `products.id`.

## Cardmarket price trends (OPTCG)
`scraper/cardmarket/` ingests Cardmarket `price_guide_*.json` market-value snapshots
(EUR) into two **isolated** tables — `cm_tracked` (sealed SKUs + singles to follow)
and `cm_prices` (time-series) — separate from the shop-scraped `products`/`snapshots`.
`track.py` = seed/add tracked items (singles resolved from a Cardmarket URL via
`resolver.py`, no scraping); `ingest.py` = idempotent upsert per `(id_product, day)`.
Inputs live in `data/cardmarket/` (raw price guides + catalogues gitignored; the small
`tracked_*.json` seed lists kept). Exposed by `GET /trends` (latest price, Δ% since
first, sparkline series) + `GET /trends/{id_product}`; the frontend **Tendances** tab
renders sealed + singles with mini-charts. Market value, **not** shop availability.

## Card valuation / speculation (OPTCG)
`scraper/valuation/` flags whether a single card is over- or under-valued.
Everything is **keyless** (apitcg was dropped — signup was broken):
- `cards_limitless.py` — the unified source: scrapes **Limitless** for rarity,
  per-**version** EUR market price (base / `aa` parallel / `manga` / `fa` / `special`),
  and alt identity, for *any* set incl. recent ones → `data/valuation/optcg_cards_limitless.json`.
  Cross-product reprints (promo/collection) are tagged `other` and excluded (not booster pulls).
  Limitless mislabels a few versions (e.g. a SEC parallel tagged `manga`, or an OP13
  god-pack red-letter print looking like a normal `aa`); `data/valuation/version_overrides.json`
  ({code:{v-number:kind}}, kinds incl. `godpack`) hand-corrects those and is applied by `load_cards`.
- `playability.py` — share-weighted card usage from the Limitless metagame
  (copies capped at 4) → `playability.json`, a 0-3 play score.
- `odds.py` — user-sourced approximate pull rates (packs per card, classic sets):
  SR 1/3 · alt 1/8 · SEC 1/30 · SP 1/144 · Event-Manga 1/288 · Manga 1/864 · godpack;
  C/UC and classic (non-parallel) leaders are not tracked. `version_tier` uses the
  card **type** (Character vs Event/Stage) so an event's parallel routes to the
  event-manga tier (1/288) rather than a character parallel (1/8). `R` uses a placeholder rate.
- `popularity.py` — character popularity from the official **WT100** reader poll
  (Shueisha 2021); a card's character name is matched to a poll rank by token
  overlap (tolerates "Monkey.D.Luffy" ↔ "Monkey D. Luffy") → a 0-1 score.
- `rank.py` — one row per tracked printing (base + each alt version); fits
  `ln(price) ~ tier + set + play + pop` (numpy OLS, R²≈0.92). The **residual is the
  mispricing signal** (over/under vs comparable cards). Displays cards ≥ a price floor.
- `model.py` — the standalone hand-weighted fair-value model (demand/supply, kept
  as an explainable reference; the ranking uses the regression instead).
Raw scraped HTML/JSON caches (`data/valuation/{limitless,apitcg}/`) are gitignored;
the small consolidated JSON is committed so `rank` runs offline.

## Data model
Core scraper tables — `sites`, `sets`, `catalog`, `products`, `snapshots` — exist
in both the raw SQLite layer (`scraper/db.py`) and as SQLAlchemy models
(`api/models/catalog.py`) that must stay column-compatible; the API adds
`users`, `favorites`, `alert_configs`, `alert_events` (API-only, `api/models/`).

- `sites`     — shops we track (host, platform, games carried).
- `sets`      — reference set catalogue per `(game, language, set_code)` from TCGdex.
- `catalog`   — canonical SKU = `(game, language, set_code, kind)` ("collection product").
- `products`  — a shop's listing of a catalog item ("site product"). Has `game`,
  `language`, `set_code`, `kind`, `catalog_id`. Stable identity `(platform, shop, platform_pid)`.
- `snapshots` — price/stock history, one row per scrape run per product.
- `users` / `favorites` / `alert_configs` / `alert_events` — accounts, watchlist
  (targets either a `product_id` or a `catalog_id`), and alert rules + a sent-event
  log used to de-duplicate restock/price-drop notifications.

## Conventions
- `language` is a first-class dimension. OPTCG/Naruto are always `'fr'`; Pokemon is
  detected per product (FR/EN/JA/KO/ZH) by `games.pokemon.detect_language`.
- **Set codes differ by language** for Pokemon (JP uses its own numbering), so set
  identity is `(game, language, set_code)`. Reference filtered to release ≥ 2020-01-01.
- Prefer a shop's JSON/API endpoint over scraping rendered HTML; fall back to
  `stealth_browser.py` (Playwright) only for anti-bot-protected shops like Micromania.
- Dev DB is SQLite (`data/tcg_stock.sqlite`, `create_all`); prod is Supabase Postgres
  via `DATABASE_URL` with `alembic upgrade head` at API startup. Keep `api/models/`
  changes paired with an Alembic migration.
- This runs against live shops — be careful with scrape frequency/concurrency.
- **Git workflow:** feature branch → PR → merge to `main` (matches Vigilyx). Show the
  commit message and wait for confirmation before `git push`; no `Co-Authored-By` trailer.
