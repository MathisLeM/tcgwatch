# TCGWatch

Suivi de stock de **produits scellés TCG** (Pokémon, One Piece / Naruto…) à travers
de nombreuses boutiques en ligne francophones. Le scraper relève prix et
disponibilité, l'API les expose, et le dashboard web alerte les acheteurs dès
qu'un produit suivi revient en stock — **au prix boutique, avant les scalpers**.

Stack (calquée sur Vigilyx) : **Next.js / Vercel** (frontend) · **FastAPI / Railway**
(API + worker scraper) · **Supabase Postgres** (DB) · **Cloudflare R2** (images).

## Architecture du dépôt (monorepo)

| Dossier | Rôle |
|---|---|
| `scraper/` | Scraper Python multi-plateformes (8 plateformes) + logique par jeu (`games/`). |
| `api/` | API FastAPI : auth (JWT+cookie), produits, sets, favoris, alertes. |
| `frontend/` | Application Next.js 16 (landing + dashboard). |
| `migrations/` | Migrations Alembic (jouées au démarrage en prod). |
| `scripts/` | Outils ponctuels (reprise SQLite→Postgres). |
| `tests/` | Tests pytest de l'API. |
| `data/` | DB SQLite locale + données de référence (TCGdex, catalog). |
| `images/` | Images produits/sets (servies depuis R2 en prod). |
| `app.py` | Ancien dashboard Streamlit (dev local uniquement, remplacé par le frontend). |

## Démarrage local

```bash
pip install -r requirements.txt
cp .env.example .env        # DATABASE_URL pointe par défaut sur data/tcg_stock.sqlite

# API (lit la SQLite existante)
uvicorn main:app --reload   # http://127.0.0.1:8000/docs

# Frontend
cd frontend && npm install && npm run dev   # http://localhost:3000

# Scraper (manuel)
python -m scraper.run --game all
python -m scraper.worker     # boucle planifiée (comme en prod)

# Tests
pytest
```

## Base de données
- **Dev** : SQLite (`data/tcg_stock.sqlite`) — `create_all` crée les tables manquantes.
- **Prod** : Supabase Postgres via `DATABASE_URL` ; `alembic upgrade head` au démarrage.
- Reprise initiale des données : voir `DEPLOYMENT.md` et
  `python -m scripts.migrate_sqlite_to_postgres`.

Voir **[DEPLOYMENT.md](DEPLOYMENT.md)** pour la mise en production.
