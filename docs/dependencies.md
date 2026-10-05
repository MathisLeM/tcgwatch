# Dépendances

## Python (3.12)

Deux fichiers :
- `requirements.txt` : ce qu'installe **Railway** (API, scraper et tests).
- `requirements-dev.txt` : `-r requirements.txt` + les outils qui ne tournent qu'en
  local. Après installation, lancer une fois `python -m playwright install chromium`.

### `requirements.txt`

| Librairie | Sert à | Utilisée dans |
|---|---|---|
| `requests` | Requêtes HTTP vers les boutiques, TCGdex, Pokecardex, Discord | tous les `discover_*` / `fetch_*`, `games/build_*`, `api/services/discord_service.py` |
| `beautifulsoup4` + `lxml` | Parsing HTML (microdata, JSON-LD, tuiles produit) | PrestaShop, WooCommerce (repli), Powerboutique, e-monsite, FantasySphere, Micromania, `micromania_parse` |
| `pandas` | Fichiers Excel de découverte et de curation, tableaux | `discover_*`, `load_curated`, `new_products`, `add_site`, `categorize_pokemon`, `app.py` |
| `openpyxl` | Lecture et écriture `.xlsx` (moteur pandas + mise en forme) | `export_excel`, `games/pokemon_catalog`, `games/pokemon_hierarchy` |
| `streamlit` | Ancien dashboard local | `app.py`, `store_stock_poc/idf_dashboard_app.py` |
| `fastapi` | Framework de l'API | `main.py`, `api/routers/` |
| `uvicorn[standard]` | Serveur ASGI | `railway.toml`, `launch_app.bat` |
| `python-multipart` | Formulaire OAuth2 du login | `api/routers/auth.py` |
| `sqlalchemy` | ORM et accès DB (SQLite et Postgres) | `api/`, `scraper/alerting.py`, `scripts/sync_to_prod.py` |
| `alembic` | Migrations du schéma prod | `migrations/`, joué au démarrage de l'API |
| `psycopg2-binary` | Driver Postgres (Supabase) | `api/database.py`, `scraper/db.py` |
| `pydantic` / `pydantic-settings` | Schémas API et config par variables d'env / `.env` | `api/schemas.py`, `api/config.py` |
| `email-validator` | Validation `EmailStr` | `api/schemas.py` (waitlist) |
| `python-jose[cryptography]` | Jetons JWT | `api/routers/auth.py` |
| `bcrypt` | Hash des mots de passe | `api/routers/auth.py`, `scripts/manage_users.py` |
| `slowapi` | Rate limiting | `api/limiter.py` (`POST /waitlist`, login) |
| `apscheduler` | Planification du worker | `scraper/worker.py` |
| `boto3` | Client S3 pour Cloudflare R2 | `api/services/r2.py`, `scraper/upload_images.py` |
| `pytest` / `httpx` | Tests, `TestClient` FastAPI | `tests/` |

### `requirements-dev.txt` (local uniquement)

| Librairie | Sert à | Utilisée dans |
|---|---|---|
| `playwright` + `playwright-stealth` | Chromium headless furtif contre Imperva / DataDome | `scraper/stealth_browser.py` → `discover_micromania`, `fetch_micromania` ; `store_stock_poc/build_idf_stores.py` |
| `numpy` | Régression OLS | `scraper/valuation/rank.py` |
| `scipy` | Corrélations de Spearman | `valuation/rank.py` (import différé), `valuation/analysis.py` |
| `matplotlib` | Graphiques d'analyse | `valuation/analysis.py` |
| `Pillow` | Redimensionnement des vignettes | `scripts/legacy/fetch_promo_pack_images.py` |

> `scraper.run --game pokemon` appelle `fetch_micromania`, qui a besoin de
> Playwright. Sans `requirements-dev.txt`, le relevé Pokémon échoue sur Micromania.

### Bibliothèque standard notable
`sqlite3` (couche brute `scraper/db.py`), `concurrent.futures` (parallélisme par
boutique), `urllib.request` (sources « keyless » : Limitless, apitcg, tcgcsv), `smtplib`
via `api/services/email_service.py`.

## Frontend (`frontend/package.json`)

| Paquet | Sert à |
|---|---|
| `next` 16.1 | Framework (App Router), déployé sur Vercel |
| `react` / `react-dom` 19.2 | UI |
| `tailwindcss` 4 + `@tailwindcss/postcss` | Styles (tokens « neon-violet » dans `app/globals.css`) |
| `typescript`, `@types/*` | Typage |
| `eslint` + `eslint-config-next` | `npm run lint` |

Pas de librairie de composants ni de graphiques : les icônes (`components/Icons.tsx`)
et les sparklines sont en SVG fait main.

## Services externes

| Service | Usage | Clé requise |
|---|---|---|
| TCGdex (`api.tcgdex.net`, `assets.tcgdex.net`) | Référentiel des sets Pokémon et logos | non |
| Pokecardex | Noms FR et logos des sets | non |
| Limitless (`onepiece.limitlesstcg.com`) | Cartes, prix et méta OPTCG (valorisation) | non |
| Cardmarket | `price_guide_*.json` et catalogues, téléchargés à la main | — |
| tcgcsv.com / TCGplayer CDN | Images des promo packs (legacy) | non |
| Supabase | Postgres prod | `DATABASE_URL` |
| Railway / Vercel | Hébergement API / frontend | dashboards |
| SMTP, Discord webhook | Alertes (optionnelles) | `SMTP_*`, `DISCORD_WEBHOOK_URL` |
| Cloudflare R2 | Images (non branché) | `R2_*` |
