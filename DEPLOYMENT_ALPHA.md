# Déploiement — Alpha privée (TCGWatch)

Version **rapide et minimale** pour faire tester l'app à quelques proches, sur la
stack Vigilyx : **GitHub → Railway (API) + Supabase (Postgres) + Vercel (frontend)**.

Choix assumés pour l'alpha (différences avec le plan cible [`DEPLOYMENT.md`](DEPLOYMENT.md)) :
- **Comptes créés à la main** (pas d'inscription publique) — `scripts/manage_users`.
- **Images servies par Railway** (logos de blocs/sets versionnés dans le repo,
  montage `/images`) — **pas de Cloudflare R2** pour l'instant.
- **Pas de worker scraper** : les données sont chargées **une fois** depuis la
  machine locale. Un seul service Railway (l'API).

Une fois en place, le cycle de travail est : **`git push` sur `main` → Railway et
Vercel redéploient tout seuls.**

---

## 0. Générer les secrets
```bash
python -c "import secrets; print(secrets.token_hex(32))"   # -> SECRET_KEY
```

## 1. Git + GitHub (fondation du « push facile »)
Le dossier n'est pas encore un dépôt git. Depuis `C:\Users\mathi\TCG_Scrapper` :
```bash
git init -b main
git add -A
git commit -m "TCGWatch alpha: scraper + API + frontend"
# Créer le repo côté GitHub (UI : github.com/new, nom "tcgwatch", privé), puis :
git remote add origin https://github.com/MathisLeM/tcgwatch.git
git push -u origin main
```
> Le `.gitignore` exclut déjà `.env`, la base SQLite locale, les dumps `data/*.xlsx`
> et `node_modules`. Il **inclut** volontairement les logos de référence
> (`images/Pokemon/Image_*`, ~10 Mo) pour que Railway les serve.

## 2. Supabase (Postgres)
1. Créer un projet Supabase.
2. Récupérer la **Connection string** (Project → Database → *Session mode*, port 5432) :
   `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`.
   → ce sera `DATABASE_URL`.

## 3. Charger les données locales → Supabase (une fois)
Depuis la machine locale, avec `DATABASE_URL` pointant sur Supabase :
```bash
# .env local temporaire OU variable d'environnement :
DATABASE_URL='postgresql://postgres:...supabase.co:5432/postgres' \
  python -m alembic upgrade head                 # crée le schéma (9 tables)
DATABASE_URL='postgresql://postgres:...supabase.co:5432/postgres' \
  python -m scripts.migrate_sqlite_to_postgres   # copie sites/sets/catalog/products/snapshots
```
(Pour rafraîchir les données plus tard : rescraper en local puis rejouer cette commande.)

## 4. Railway — service API (unique)
1. **New Project → Deploy from GitHub repo** → le repo `tcgwatch`.
   `railway.toml` est détecté (nixpacks, `uvicorn main:app`, healthcheck `/health`).
2. **Variables** (Settings → Variables) :
   ```
   ENVIRONMENT=production
   DATABASE_URL=<connection string Supabase>
   SECRET_KEY=<le token généré à l'étape 0>
   ALLOW_PUBLIC_SIGNUP=false
   ALLOWED_ORIGINS=https://<ton-app>.vercel.app
   APP_URL=https://<ton-app>.vercel.app
   ```
   (Alertes email/Discord : optionnel pour l'alpha — laisser `SMTP_HOST` vide.)
3. Au démarrage l'app joue `alembic upgrade head` et refuse de booter si
   `SECRET_KEY` est resté le placeholder.
4. Noter l'URL publique du service (ex. `https://tcgwatch-api.up.railway.app`).

> Les images sont servies par ce service sur `…/images/...` (montage statique),
> donc rien d'autre à configurer côté images.

## 5. Vercel — frontend
1. **Add New → Project** → importer le repo, **Root Directory = `frontend`**
   (Next.js auto-détecté).
2. **Environment Variables** :
   ```
   NEXT_PUBLIC_API_URL=https://<url-railway-de-l-api>
   ```
   (Ne **pas** définir `NEXT_PUBLIC_ALLOW_SIGNUP` → l'inscription reste cachée.)
3. Déployer, puis reporter l'URL Vercel dans `ALLOWED_ORIGINS` / `APP_URL` côté
   Railway (étape 4.2) et redéployer l'API.

## 6. Créer les comptes des testeurs
Depuis la machine locale, contre la base **Supabase** :
```bash
DATABASE_URL='postgresql://postgres:...supabase.co:5432/postgres' \
  python -m scripts.manage_users create moi@example.com --admin
DATABASE_URL='postgresql://postgres:...supabase.co:5432/postgres' \
  python -m scripts.manage_users create ami@example.com          # mot de passe généré + affiché
```
Autres commandes : `list`, `passwd <email>`, `deactivate <email>`, `delete <email>`.
Transmets à chaque proche : l'URL Vercel + son email + son mot de passe.

---

## Cycle de travail quotidien (local → prod)
```bash
# modifications locales, tester :  uvicorn main:app --reload  +  (cd frontend && npm run dev)
git add -A && git commit -m "…"
git push                # Railway (API) et Vercel (frontend) redéploient automatiquement
```
- Changement de schéma DB → ajouter une migration Alembic (jouée au boot Railway).
- Rafraîchir les données → rescraper en local, puis `migrate_sqlite_to_postgres`.

## Checklist go-live
- [ ] `GET https://<api>/health` répond `200`
- [ ] `GET https://<api>/images/Pokemon/Image_block/bloc-mega-evolution.png` renvoie une image
- [ ] login (compte créé à l'étape 6) → dashboard + Catalogue chargent
- [ ] les images de blocs/sets s'affichent dans **Catalogue**
- [ ] la page `/login` ne montre **pas** le lien d'inscription

## Passage au plan cible (plus tard)
Quand l'alpha est validée : ajouter le **worker** Railway (`railway.worker.toml`)
pour le rescrape auto, et **Cloudflare R2** pour toutes les images — voir
[`DEPLOYMENT.md`](DEPLOYMENT.md).
