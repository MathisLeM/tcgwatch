# TCG_Scrapper — frontend

Next.js 16 (App Router) + React 19 + TypeScript landing/app for **TCGWatch**, a
multi-TCG (Pokémon, One Piece, …) sealed-product stock & price tracker. The public
site is **in French** (target audience is the French market). Styling via Tailwind
CSS v4. Same stack & deploy target
as the sibling project **Vigilyx** (`C:\Users\mathi\vigilyx\frontend`): Vercel
for the frontend, FastAPI on Railway + Supabase Postgres + Cloudflare R2 for the
backend. L'API FastAPI existe (`api/`) et tourne en local sur `:8000`.

## Run
- Dev:    `npm run dev`
- Build:  `npm run build`  ·  Start: `npm run start`
- Lint:   `npm run lint`   (ESLint, `eslint-config-next`)

## Layout
- `app/page.tsx`    — public landing page, **French** (hero + collage produits, chiffres clés,
  manifeste, fonctionnalités, comment ça marche, communauté, tarifs, personas, waitlist).
  Portage de la maquette Claude Design « Landing v2 » (projet *Refonte landing TCG Scrapper*).
- `app/layout.tsx`  — root layout + SEO metadata (Geist corps + Bricolage Grotesque titres, dark theme).
- `app/globals.css` — Tailwind v4 entry + theme tokens (palette « neon-violet », breakpoint `wide:`).
- `app/dashboard`   — portage de la maquette « Dashboard v2 » : table ≥ 860px, cartes en
  dessous (variant `wide:`), vignette produit, badge statut, delta de prix et sparkline
  30 j. Lit `set_code`/`language`/`kind` depuis l'URL pour le deep-link du catalogue.
- `app/catalog`     — **Catalogue**: block > set > article-type drill-down (`fetchCatalog`
  → `GET /catalog`). Clicking an article type links to the dashboard filtered on that set.
- `components/`      — `LandingNav` (client : nav sticky + menu mobile), `Icons`
  (jeu d'icônes SVG inline partagé landing + app, pas de dépendance externe),
  `AppNav` (header applicatif : pastilles de nav, pastilles scrollables en mobile),
  `Protected` (auth gate + `AppNav` + le `<main>` de toutes les pages applicatives).
- `lib/api.ts`       — typed fetch wrappers. `imageUrl(path)` turns a root-relative reference
  image path (`images/Pokemon/...` from the API) into an absolute, URL-encoded `${API}/…` URL;
  the backend serves these via a `/images` static mount (Cloudflare R2 in prod).
- `lib/brand.ts`     — product name / tagline / site URL (rename the brand here).

## Conventions
- App Router, server components by default — only add `"use client"` when a
  component needs hooks/state/effects.
- Backend calls go through a single `lib/api.ts` wrapper — don't scatter raw
  `fetch` in components (mirrors Vigilyx).
- Une seule palette pour **tout** le projet : les tokens « neon-violet » de
  `globals.css` (`bg-canvas`, `bg-panel`, `bg-panel-2`, `border-line`/`line-strong`,
  `text-ink/muted/dim`, `accent`/`gold`/`ok`). Plus aucune classe `gray-*`/`red-*`/
  `amber-*` dans `app/` ni `components/` — un `grep` doit rester vide.
- Texte sur un aplat `bg-accent`/`bg-gold` : utiliser `text-on-accent`/`text-on-gold`.
  L'accent est **clair** dans cette palette, du blanc dessus tomberait à ~2:1.
- Les variantes « braise » et « nuit-dorée » des maquettes sont documentées en
  commentaire dans `globals.css` : changer les `--color-*` bascule tout d'un coup.
- Titres de la landing en `font-display` (Bricolage Grotesque), corps en `font-sans` (Geist).
- Le dashboard bascule table ↔ cartes au variant **`wide:`** (860px, défini dans
  `globals.css`) — ce n'est pas un breakpoint Tailwind standard.
- Les vignettes servies par l'API passent par `imageUrl()` + un `<img>` simple
  (l'hôte est l'API, pas le pipeline `next/image`) — même convention que `/catalog`.
- Public-facing copy is **French**. `BRAND`/`TAGLINE` live in `lib/brand.ts` ("TCGWatch").

## Deployment (en ligne depuis fin juillet 2026)
- **Frontend** → Vercel, **déployé** : https://tcgwatch.vercel.app (Next.js
  auto-détecté, pas de `vercel.json`). Push sur `main` = deploy.
- **Backend** → Railway, **déployé** : https://tcgwatch-production.up.railway.app.
  `NEXT_PUBLIC_API_URL` est réglée sur cette URL côté Vercel (en local, `.env.local`
  pointe sur `http://localhost:8000`). **DB** → Supabase Postgres (free tier : se met
  en pause après ~7 j sans trafic → toutes les pages app cassent, il faut la réveiller).
- **Object storage** → Cloudflare R2 **pas encore branché** : les images de référence
  sont servies par le mount `/images` de Railway. **Secrets** dans les dashboards,
  jamais dans le repo.
- ⚠️ Le formulaire waitlist de `app/page.tsx` est en `action="#"` — il ne collecte
  rien. À brancher avant toute campagne d'acquisition.
- **Git workflow:** feature branch → PR → merge to `main`. Show commit messages
  before pushing; no Co-Authored-By trailers (matches Vigilyx).
