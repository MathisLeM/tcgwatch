# Déploiement TCGWatch

> **Juste besoin de mettre en ligne une alpha pour quelques testeurs ?** Suivez
> plutôt [`DEPLOYMENT_ALPHA.md`](DEPLOYMENT_ALPHA.md) : version minimale (API
> Railway + Supabase + Vercel, images servies par Railway, comptes créés à la
> main, pas de worker). Ce document-ci est le plan **cible** complet.

Stack identique à Vigilyx : **GitHub → Vercel (frontend) + Railway (API + worker
scraper) + Supabase (Postgres) + Cloudflare R2 (images)**. Tout le code est prêt ;
ce guide couvre le provisioning et la mise en ligne.

> Ordre conseillé : Supabase → (reprise des données) → Railway API → Railway worker
> → R2 → Vercel → domaine.

## 0. Pré-requis
- Repo GitHub `tcgwatch` poussé sur `main` (branche → PR → main ; pas de trailer Co-Authored-By).
- Secrets générés :
  - `SECRET_KEY` : `python -c "import secrets; print(secrets.token_hex(32))"`

## 1. Supabase (Postgres)
1. Créer un projet Supabase, récupérer la **Connection string** (mode *session*),
   format `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`.
2. Elle servira de `DATABASE_URL` côté Railway (API **et** worker).

## 2. Reprise des données locales → Supabase
Depuis la machine locale, `.env` pointant `DATABASE_URL` sur Supabase :
```bash
python -m alembic upgrade head                 # crée le schéma sur Postgres
python -m scripts.migrate_sqlite_to_postgres   # copie sites/sets/catalog/products/snapshots
```
(Le script re-synchronise les séquences Postgres ; `--dry-run` pour vérifier d'abord.)

## 3. Railway — service API
- Nouveau service depuis le repo GitHub. `railway.toml` est détecté (nixpacks,
  `uvicorn main:app`, healthcheck `/health`).
- Variables d'environnement :
  - `ENVIRONMENT=production`
  - `DATABASE_URL=<supabase>`
  - `SECRET_KEY=<random>`
  - `ALLOWED_ORIGINS=https://<domaine-frontend>`
  - (alertes) `SMTP_HOST/PORT/USER/PASS`, `FROM_EMAIL`
  - (images) `R2_*` (voir §5)
- Au démarrage, l'app joue `alembic upgrade head` et refuse de booter si
  `SECRET_KEY` est resté la valeur par défaut.

## 4. Railway — service worker (scraper)
- 2ᵉ service, même repo. Dans *Settings → Config file path* : `railway.worker.toml`
  (start `python -m scraper.worker`).
- Mêmes `DATABASE_URL` / `R2_*`. Cadence via `SCRAPE_INTERVAL_HOURS` (déf. 6) et
  `SCRAPE_GAMES` (`all`).

## 5. Cloudflare R2 (images)
1. Créer un bucket (ex. `tcgwatch-images`) + un token API R2 (Access Key / Secret).
2. Activer un accès public (domaine personnalisé `img.tcgwatch.app` ou URL r2.dev).
3. Variables (API + worker) : `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_BASE_URL`.
4. Upload initial des images : `python -m scraper.upload_images` (voir M4).

## 6. Vercel (frontend)
- Importer le repo, **Root Directory = `frontend`** (Next.js auto-détecté).
- Variable : `NEXT_PUBLIC_API_URL=https://<api-railway>`.
- Push sur `main` = redeploy.

## 7. Domaine
- Acheter le domaine, le brancher sur Vercel (frontend) ; sous-domaine `api.` →
  Railway, `img.` → R2. Mettre à jour `ALLOWED_ORIGINS` et `NEXT_PUBLIC_API_URL`.

## Coûts indicatifs
Railway ~7-10 $/mois · Vercel gratuit · Supabase 0-25 $ · R2 gratuit (faible volume).

## Checklist go-live
- [ ] `/health` répond 200 sur Railway
- [ ] signup → login → /auth/me (cookie posé, cross-domain OK)
- [ ] dashboard charge produits + images R2
- [ ] worker écrit de nouveaux snapshots (logs Railway)
- [ ] une alerte de test arrive par Email **et** Discord
