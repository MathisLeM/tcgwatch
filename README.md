# TCGWatch

Suivi du **stock et du prix des produits scellés TCG** (Pokémon, One Piece,
Naruto Mythos) sur une centaine de boutiques en ligne francophones. Le
scraper relève prix et disponibilité, l'API les expose, et l'application web
permet de suivre ses produits et d'être alerté d'un restock — **au prix boutique,
avant les scalpers**.

- Application : https://tcgwatch.vercel.app
- API : https://tcgwatch-production.up.railway.app (`/health`)
- Code : https://github.com/MathisLeM/tcgwatch

Stack (calquée sur Vigilyx) : **Next.js / Vercel** (frontend) · **FastAPI / Railway**
(API) · **Supabase Postgres** (DB prod) · **SQLite** (DB locale, source de vérité
des données scrapées).

> **Statut : alpha privée.** La prod est un *miroir* de la base SQLite locale : on
> scrape sur le poste puis on pousse avec `scripts/sync_to_prod.py`. Pas de worker
> automatique, pas de R2, comptes créés à la main. Voir [docs/architecture.md](docs/architecture.md).

## Démarrage rapide

```bash
# Python 3.12
pip install -r requirements.txt          # API + scraper (ce qu'installe Railway)
pip install -r requirements-dev.txt      # + Playwright, valorisation, outils locaux
python -m playwright install chromium    # une fois (Micromania)

# Application locale complète (API :8000 + frontend :3000) sur la SQLite locale
launch_app.bat
#   ou à la main :
uvicorn main:app --reload                # http://127.0.0.1:8000/docs
cd frontend && npm install && npm run dev  # http://localhost:3000

# Tests
pytest
```

Aucune variable d'environnement n'est nécessaire en local : par défaut tout lit
et écrit `data/tcg_stock.sqlite`. Le modèle `.env.example` liste les variables
de prod.

## Le cycle de routine

```bash
python -m scraper.run --game all         # 1. nouveau relevé prix/stock (ou launch_scraping_*.bat)
python -m scraper.cardmarket.ingest      # 2. (optionnel) cotes Cardmarket si nouveau price_guide
launch_sync_prod.bat                     # 3. dry-run puis push vers Supabase
```

Tous les enchaînements (ajout d'une boutique, nouveaux produits, catalogue
Pokémon, valorisation, comptes…) sont décrits dans [docs/workflows.md](docs/workflows.md).

## Documentation

| Document | Contenu |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Vue d'ensemble, flux de données, modèle de données, API, état du déploiement |
| [docs/workflows.md](docs/workflows.md) | **Ordres d'exécution** : quoi lancer, dans quel ordre, pour chaque tâche |
| [docs/scripts.md](docs/scripts.md) | Référence de **chaque script** : rôle, commande, arguments, entrées/sorties |
| [docs/dependencies.md](docs/dependencies.md) | Librairies Python et JS utilisées, et par quoi |
| [docs/data.md](docs/data.md) | Contenu de `data/` et `images/` : versionné ou non, régénérable ou non |
| [DEPLOYMENT_ALPHA.md](DEPLOYMENT_ALPHA.md) | Déploiement actuel (Railway + Supabase + Vercel) |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Plan cible complet (worker, R2, domaine) |
| [frontend/CLAUDE.md](frontend/CLAUDE.md) | Conventions du frontend Next.js |

## Organisation du dépôt

| Dossier | Rôle |
|---|---|
| `scraper/` | Scraper multi-plateformes (9 plateformes e-commerce) + logique par jeu (`games/`), cotes Cardmarket (`cardmarket/`), valorisation des cartes (`valuation/`), scripts historiques (`legacy/`) |
| `api/` | API FastAPI : auth (JWT en cookie), produits, sets, catalogue, tendances, favoris, alertes, liste d'attente |
| `frontend/` | Application Next.js 16 (landing + dashboard) |
| `scripts/` | Outils d'admin : `sync_to_prod`, `manage_users` ; one-shot dans `scripts/legacy/` |
| `migrations/` | Migrations Alembic (jouées au démarrage de l'API en prod) |
| `tests/` | Tests pytest (API + logique scraper) |
| `store_stock_poc/` | POC isolé : stock en magasin Fnac / King Jouet / Cultura (non branché) |
| `data/` | SQLite locale + données de référence — voir [docs/data.md](docs/data.md) |
| `images/` | Logos de blocs/sets et visuels produits servis par l'API (`/images`) |
| `docs/` | Documentation + registre des boutiques (`boutiques_optcg.xlsx`) |
| `main.py` | Point d'entrée de l'API (`uvicorn main:app`) |
| `app.py` | Ancien dashboard Streamlit, local uniquement (`launch_dashboard.bat`) |
| `launch_*.bat` | Raccourcis Windows — voir [docs/scripts.md](docs/scripts.md#raccourcis-windows-launch_bat) |
