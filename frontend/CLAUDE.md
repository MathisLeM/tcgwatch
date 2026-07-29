# TCG_Scrapper — frontend

Next.js 16 (App Router) + React 19 + TypeScript landing/app for **TCGWatch**, a
multi-TCG (Pokémon, One Piece, …) sealed-product stock & price tracker. The public
site is **in French** (target audience is the French market). Styling via Tailwind
CSS v4. Same stack & deploy target
as the sibling project **Vigilyx** (`C:\Users\mathi\vigilyx\frontend`): Vercel
for the frontend, FastAPI on Railway + Supabase Postgres + Cloudflare R2 for the
backend (backend not built yet).

## Run
- Dev:    `npm run dev`
- Build:  `npm run build`  ·  Start: `npm run start`
- Lint:   `npm run lint`   (ESLint, `eslint-config-next`)

## Layout
- `app/page.tsx`    — public landing page, **French** (hero, features, how-it-works, waitlist).
- `app/layout.tsx`  — root layout + SEO metadata (Geist font, dark theme).
- `app/globals.css` — Tailwind v4 entry + theme tokens.
- `app/dashboard`   — product table (filters, favorites). Reads `set_code`/`language`/`kind`
  from the URL so `/sets` can deep-link into a pre-filtered view.
- `app/sets`        — **Catalogue**: block > set > article-type drill-down (`fetchBlocks`
  → `GET /sets/blocks`). Clicking an article type links to the dashboard filtered on that set.
- `components/`      — `LandingNav`, `AppNav` (auth header, links Dashboard/Catalogue/Favoris/Alertes),
  `Protected` (auth gate + renders `AppNav`).
- `lib/api.ts`       — typed fetch wrappers. `imageUrl(path)` turns a root-relative reference
  image path (`images/Pokemon/...` from the API) into an absolute, URL-encoded `${API}/…` URL;
  the backend serves these via a `/images` static mount (Cloudflare R2 in prod).
- `lib/brand.ts`     — product name / tagline / site URL (rename the brand here).

## Conventions
- App Router, server components by default — only add `"use client"` when a
  component needs hooks/state/effects.
- Backend calls (once the API exists) go through a single `lib/api.ts` wrapper —
  don't scatter raw `fetch` in components (mirrors Vigilyx).
- Keep the dark theme: `bg-gray-950` base, red/amber accents for this project.
- Public-facing copy is **French**. `BRAND`/`TAGLINE` live in `lib/brand.ts` ("TCGWatch").

## Deployment (planned, same as Vigilyx)
- **Frontend** → Vercel (Next.js auto-detected, no `vercel.json`). Push = deploy.
- **Backend** → Railway (FastAPI/uvicorn). **DB** → Supabase Postgres.
  **Object storage** → Cloudflare R2. **Secrets** live in dashboards, never the repo.
- **Git workflow:** feature branch → PR → merge to `main`. Show commit messages
  before pushing; no Co-Authored-By trailers (matches Vigilyx).
