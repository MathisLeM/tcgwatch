# Données (`data/`, `images/`)

Légende : ✅ versionné dans git · 💾 local uniquement (gitignoré) · ♻️ régénérable par
un script · ✋ édité à la main (**à sauvegarder**).

## `data/`

| Chemin | Statut | Contenu / producteur |
|---|---|---|
| `tcg_stock.sqlite` | 💾 ✋ | **La base locale, source de vérité** (produits, ~66 k snapshots depuis mai 2026). Non régénérable : à sauvegarder |
| `extra_shops.json` | ✅ ✋ | Boutiques ajoutées après coup (lu par `shop_registry`, écrit par `add_site`) |
| `pokemon_catalog.xlsx` | ✅ ✋ | Grille des SKU Pokémon suivis (`games.pokemon_catalog export` / `load`) |
| `discovered_<plateforme>.xlsx` | 💾 ✋ | Découvertes **curées** (colonne `set`) relues par `load_curated`. Seuls shopify, prestashop et woocommerce existent en local |
| `discovered_pokemon_raw.xlsx`, `discovered_pokemon.xlsx` | 💾 ♻️ | Sorties de `discover_pokemon` et `categorize_pokemon` |
| `ignored_products.json` | 💾 ✋ | Produits marqués DROP dans `new_products` (ne reviennent plus) |
| `new_products.xlsx` | 💾 ♻️ | Fichier de revue temporaire de `new_products` |
| `review_<host>.xlsx` | 💾 ♻️ | Fichier de revue temporaire de `add_site` |
| `products_view.xlsx` | 💾 ♻️ | Export lisible (`scraper.export_excel`) |
| `optcg_promo_packs.{json,xlsx}` | 💾 ♻️ | Sortie de `scripts/legacy/build_promo_packs.py` |

### `data/reference/`

| Chemin | Statut | Contenu |
|---|---|---|
| `pokemon_sets.json` | ✅ ♻️ | Référentiel TCGdex (`games.build_pokemon_sets`), lu au runtime par `games/pokemon.py` |
| `pokemon_series.json`, `pokemon_set_dictionary.xlsx` | ✅ ♻️ | `games.build_pokemon_dictionary` |
| `pokemon_hierarchy.{json,xlsx}` | ✅ ♻️ | `games.pokemon_hierarchy` |
| `pokecardex_sets.json` | ✅ ♻️ | `games.build_pokecardex` |
| `cardmarket/` | 💾 | Dump Cardmarket Pokémon (non-singles + price guide), utilisé par `games.cardmarket` |
| `limitless_promo_cache/`, `tcgplayer_*.json` | 💾 ♻️ | Caches des scripts legacy des promo packs |

### `data/cardmarket/` (cotes OPTCG)

| Chemin | Statut | Contenu |
|---|---|---|
| `tracked_products.json`, `tracked_singles.json` | ✅ ✋ | Listes de départ pour `cardmarket.track seed` |
| `price_guide/price_guide_<jjmm>.json` | 💾 | Price guides téléchargés à la main, ingérés par `cardmarket.ingest` |
| `products_{singles,nonsingles}_*.json` | 💾 | Catalogues Cardmarket utilisés par `resolver` |

### `data/valuation/`

| Chemin | Statut | Contenu |
|---|---|---|
| `optcg_cards_limitless.json` | ✅ ♻️ | Source consolidée (`valuation.cards_limitless`), versionnée pour que `rank` tourne hors ligne |
| `playability.json` | ✅ ♻️ | `valuation.playability` |
| `version_overrides.json` | ✅ ✋ | Corrections manuelles des versions mal étiquetées par Limitless |
| `optcg_cards.json` | ✅ | Ancien catalogue apitcg (`scraper/legacy/apitcg_rarity.py`) |
| `limitless/`, `apitcg/` | 💾 ♻️ | Caches HTML et JSON bruts |
| `analysis/` | 💾 ♻️ | Graphiques de `valuation.analysis` |

## `images/`

Servi par l'API sur `/images/...`, avec le même chemin relatif.

| Chemin | Statut | Contenu |
|---|---|---|
| `Pokemon/Image_block/`, `Pokemon/Image_Serie/` | ✅ ✋ | Visuels curés à la main (jamais écrasés par les scripts) |
| `Pokemon/Image_Serie_auto/` | ✅ ♻️ | Logos TCGdex (`fetch_set_images`) |
| `Pokemon/Image_Serie_pokecardex/` | ✅ ♻️ | Logos Pokecardex (`fetch_pokecardex_images`) |
| `OP*`, `EB*`, `PRB*`, `NRT*` (racine) | ✅ ✋ | Visuels OPTCG / Naruto : `<SET>BB` = display, `SB` = booster, `SPC` = case |
| `Pokemon/Booster de *.png`, `Logos/`, `promo_packs/` | 💾 | Visuels locaux non publiés (logos de marque, promo packs) |

Les visuels de la landing sont copiés dans `frontend/public/images/` (versionnés).

## Hors dépôt

`C:\Users\mathi\TCG_Scrapper_archive\` contient ce qui a été retiré lors du
nettoyage du 2026-10-05 : sauvegardes SQLite, dump Cardmarket `OP26062026/` (requis
par `build_promo_packs`), fichiers `review_*.xlsx`, captures du POC Micromania. Le
détail est dans son `README.txt`.
