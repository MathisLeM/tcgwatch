# TCG_Scrapper (TCGWatch)

Tracks stock/price of **sealed TCG products** across many French online shops.
Multi-game: **OPTCG / Naruto Mythos** (French only) and **Pokemon TCG**
(multi-language: FR / EN / JA / KO / ZH). Started as a Streamlit scraper, has
since grown into a full monorepo product ("TCGWatch") built on the same stack
as the sibling project **Vigilyx** (`C:\Users\mathi\vigilyx`): **Next.js**
(frontend) · **FastAPI** (API + worker) · **SQLAlchemy/Postgres-compatible DB**
· S3-compatible image storage.

**Nothing is deployed yet — the project runs entirely locally.** Railway
(API + worker) / Vercel (frontend) / Supabase (Postgres) / Cloudflare R2
(images) are the *planned* production targets (see `DEPLOYMENT.md`), not a
live environment: there's no prod DB, no deployed API, no domain. Local dev
uses SQLite (`data/tcg_stock.sqlite`) end-to-end and `uvicorn --reload` /
`npm run dev`. Treat `DEPLOYMENT.md` as a runbook to follow later, not a
description of current state.

The scraper (9 platform fetchers, game-agnostic) is the original core and still
runs standalone; `api/` + `frontend/` are the newer product layer built on top
of the same local SQLite data. `app.py` (Streamlit) is the legacy local-only
dashboard, superseded by `frontend/` but kept for quick local inspection.

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
- Legacy Streamlit dashboard: `streamlit run app.py` (or `launch_dashboard.bat`)
- Migrate old OPTCG DB: `python -m scraper.migrate_from_optcg`
- Migrate SQLite → Postgres (one-time, only needed once actually deploying): `python -m scripts.migrate_sqlite_to_postgres`
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
  `notify.py` = channel dispatch, `r2.py` = image upload, `listings.py`, `store_inventory.py`),
  `retailers.py` = curated registry of big retail chains (live/soon/blocked, for the
  "grandes enseignes" UI overlay — separate from the scraped `sites` table).
- `frontend/`       — Next.js 16 / React 19 / TypeScript app (see `frontend/CLAUDE.md`;
  update that file too when frontend conventions change — it currently says the
  backend isn't built, which is now stale).
- `migrations/`     — Alembic migrations, run automatically at API startup in prod.
- `scripts/`        — one-off tools: `migrate_sqlite_to_postgres.py`,
  `build_promo_packs.py`, `fetch_promo_pack_images.py`, `merge_optcg_history.py`.
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
