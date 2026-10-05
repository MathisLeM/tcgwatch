# Workflows — ordres d'exécution

Toutes les commandes se lancent **depuis la racine du projet** (`python -m …`).
Par défaut elles lisent et écrivent la SQLite locale `data/tcg_stock.sqlite`.
Pour viser Supabase, on définit `DATABASE_URL` ponctuellement. On ne la laisse
**jamais** en place dans `.env` : `scraper.run` écrirait alors directement en prod.

```powershell
# PowerShell : variable pour la session courante seulement
$env:DATABASE_URL = "postgresql://postgres:...@db.<ref>.supabase.co:5432/postgres"
python -m scripts.sync_to_prod --dry-run
Remove-Item Env:DATABASE_URL
```

---

## 1. Routine : rafraîchir les prix et pousser en prod

| # | Commande | Raccourci |
|---|---|---|
| 1 | `python -m scraper.run --game optcg` | `launch_scraping_optcg.bat` |
| 1 | `python -m scraper.run --game pokemon` (lance Chromium pour Micromania) | `launch_scraping_pokemon.bat` |
| 2 | `python -m scraper.export_excel` → `data/products_view.xlsx` (optionnel, les `.bat` le font) | — |
| 3 | `python -m scripts.sync_to_prod --dry-run`, puis la même commande sans `--dry-run` | `launch_sync_prod.bat` |

`scraper.run` affiche à la fin les restocks, les ruptures et les variations de prix
depuis le relevé précédent. Les alertes utilisateurs (`scraper.alerting`) ne
partent que depuis le worker, qui n'est pas déployé.

## 2. Repérer les nouveaux produits des boutiques déjà suivies (OPTCG / Naruto)

`launch_new_products.bat`, ou à la main :

1. `python -m scraper.new_products generate` : relance la découverte sur toutes
   les boutiques et écrit les nouveautés dans `data/new_products.xlsx`.
2. Ouvrir le fichier et mettre `KEEP` ou `DROP` dans la colonne `decision`. Pour
   chaque `KEEP`, remplir `set` (ex. `OP12`, `PRB02`). Enregistrer et fermer.
3. `python -m scraper.new_products apply` : les `KEEP` entrent dans `products`, les
   `DROP` vont dans `data/ignored_products.json` et ne reviendront plus.
4. Prochain `scraper.run` : les nouveaux produits reçoivent leur premier snapshot.

## 3. Ajouter une nouvelle boutique

`launch_add_site.bat` (`python -m scraper.add_site`), en mode interactif :

1. Saisir l'URL et le nom. Le script détecte la plateforme (Shopify, PrestaShop
   ou WooCommerce ; sinon il s'arrête).
2. Il lance la découverte sur cette boutique, applique `cleanup` et écrit
   `data/review_<host>.xlsx`.
3. **Pause** : supprimer les lignes indésirables dans l'Excel, enregistrer, valider.
4. Le script ajoute les lignes à `data/discovered_<plateforme>.xlsx`, enregistre la
   boutique dans `data/extra_shops.json` et recharge la base (`load_curated`).

Pour les autres plateformes (Wix, Powerboutique, e-monsite, Next.js, FantasySphere),
il faut déclarer la boutique dans `data/extra_shops.json`, lancer
`python -m scraper.discover_<plateforme>`, curer l'Excel produit, puis lancer
`python -m scraper.load_curated`.

Pense à tenir à jour le registre `docs/boutiques_optcg.xlsx` (statut Tracked ou
Skipped, avec la raison).

## 4. Pokémon : référentiel et catalogue (à refaire à chaque nouvelle extension)

| # | Commande | Produit |
|---|---|---|
| 1 | `python -m scraper.games.build_pokemon_sets` | `data/reference/pokemon_sets.json` + table `sets` (TCGdex) |
| 2 | `python -m scraper.games.build_pokemon_dictionary` | `pokemon_series.json` + `pokemon_set_dictionary.xlsx` |
| 3 | `python -m scraper.games.cardmarket` | rapport des types de produits par set (dump Cardmarket requis) |
| 4 | `python -m scraper.games.pokemon_catalog export` | `data/pokemon_catalog.xlsx`. **Éditer à la main** : un `x` dans une cellule = SKU suivi |
| 5 | `python -m scraper.games.pokemon_catalog load` | upsert de la table `catalog` (les SKU décochés sont retirés) |
| 6 | `python -m scraper.fetch_set_images` | logos manquants depuis TCGdex → `images/Pokemon/Image_Serie_auto/` |
| 6b | `python -m scraper.games.build_pokecardex` puis `python -m scraper.fetch_pokecardex_images` | noms FR et logos Pokecardex → `Image_Serie_pokecardex/` |
| 7 | `python -m scraper.games.pokemon_hierarchy` | arbre bloc > set > type (`pokemon_hierarchy.json` / `.xlsx`) |

## 5. Pokémon : découverte des produits en boutique

> ⚠️ **Destructif.** `categorize_pokemon` commence par
> `DELETE FROM products WHERE game='pokemon' AND platform != 'micromania'`. Les
> `snapshots` sont en `ON DELETE CASCADE` : **tout l'historique de prix Pokémon
> (hors Micromania) est effacé** et les produits sont recréés avec de nouveaux ids.
> Avant de le lancer, faire une copie de `data/tcg_stock.sqlite`.

1. `python -m scraper.discover_pokemon` : extraction brute de toutes les boutiques
   vers `data/discovered_pokemon_raw.xlsx` (sans filtre).
2. `python -m scraper.categorize_pokemon` : garde le scellé, détecte la langue, le
   set et le type, écarte les autres TCG, écrit `data/discovered_pokemon.xlsx` et
   **charge en base** (produits + un premier snapshot).
3. Micromania, séparément (navigateur) : `python -m scraper.discover_micromania`
   (`--dry-run` / `--limit N` pour tester).
4. Rejouer l'étape 7 du workflow 4 pour mettre à jour les compteurs de l'arbre.

## 6. Cotes Cardmarket (onglet « Tendances »)

1. Déposer le nouveau fichier `price_guide_<jjmm>.json` dans `data/cardmarket/price_guide/`.
   Les catalogues `products_singles_*.json` / `products_nonsingles_*.json` vont dans
   `data/cardmarket/` (ils servent à la résolution d'URL).
2. Première fois seulement : `python -m scraper.cardmarket.track seed`.
3. `python -m scraper.cardmarket.ingest` (tous les fichiers) ou
   `python -m scraper.cardmarket.ingest price_guide_1307.json`. C'est idempotent.
4. Suivre une carte de plus : `python -m scraper.cardmarket.track add-single <url-cardmarket>`,
   puis relancer `ingest` pour remplir l'historique.
5. Pousser : `sync_to_prod` (tables `cm_tracked` / `cm_prices`).

## 7. Valorisation des cartes OPTCG (local, hors application)

1. `python -m scraper.valuation.cards_limitless OP15 OP16 EB03` : cartes, versions et
   prix depuis Limitless (HTML mis en cache dans `data/valuation/limitless/`).
2. `python -m scraper.valuation.playability` : usage en méta → `playability.json`.
3. `python -m scraper.valuation.rank --all` : classement sur/sous-valorisé
   (`--cv 5` pour une validation croisée).
4. Optionnel : `python -m scraper.valuation.analysis` → graphiques dans `data/valuation/analysis/`.

Corrections manuelles de versions mal étiquetées : `data/valuation/version_overrides.json`.

## 8. Comptes utilisateurs (alpha)

Contre la prod (avec `DATABASE_URL` défini pour la session, cf. en-tête) :

```bash
python -m scripts.manage_users create ami@example.com          # mot de passe généré et affiché
python -m scripts.manage_users create moi@example.com --admin
python -m scripts.manage_users list | passwd | activate | deactivate | delete <email>
```

## 9. Développement

| Action | Commande |
|---|---|
| App complète locale | `launch_app.bat` (API :8000 + front :3000, SQLite locale) |
| API seule | `uvicorn main:app --reload` |
| Front seul | `cd frontend && npm run dev` (ou `launch_landing.bat`) |
| Tests | `pytest` |
| Lint front | `cd frontend && npm run lint` |
| Changement de schéma | modifier `api/models/` **et** `scraper/db.py`, puis `alembic revision -m "…"` et écrire la migration à la main. Elle est jouée au démarrage de Railway |
| Livrer | branche → PR → merge sur `main` : Railway et Vercel redéploient automatiquement |
