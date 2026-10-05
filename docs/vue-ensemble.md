# TCGWatch en une page

## À quoi ça sert

Les produits scellés de jeux de cartes (displays, boosters, coffrets Pokémon,
One Piece, Naruto) sont souvent en rupture, puis revendus plus cher par des
spéculateurs. TCGWatch surveille une centaine de boutiques en ligne françaises et
indique **où un produit est disponible, et à quel prix**. L'objectif est de
pouvoir l'acheter au prix boutique, avant les revendeurs.

## Comment ça marche, en quatre étapes

**1. Trouver les produits.** Une fois par boutique, un script parcourt son
catalogue et liste les produits scellés. On relit cette liste à la main pour ne
garder que les bons produits, chacun rattaché à son extension (par exemple « OP12 »
ou « Évolutions Prismatiques »). Les boutiques tournent sur des logiciels différents
(Shopify, WooCommerce, PrestaShop…) : le projet sait lire chacun de ces 9 types de
sites.

**2. Relever les prix.** Régulièrement, le scraper repasse sur chaque produit connu
et note son prix et s'il est en stock. Chaque passage est conservé : on obtient un
**historique** qui permet de voir les retours en stock et les baisses de prix.

**3. Publier.** Ces relevés sont faits sur l'ordinateur du mainteneur et stockés
dans une base locale. Une commande les recopie ensuite vers la base en ligne,
utilisée par le site.

**4. Consulter.** Le site web (https://tcgwatch.vercel.app) affiche les produits,
leur prix, leur disponibilité et leur évolution sur 30 jours. On peut naviguer par
jeu, par extension et par type de produit, et suivre ses favoris.

```
 Boutiques en ligne ──► Scraper ──► Base locale ──► Base en ligne ──► API ──► Site web
                      (relevés)     (ordinateur)    (Supabase)       (Railway) (Vercel)
```

## Ce qu'il y a en plus

- **Cotes du marché** : en complément des prix boutique, le site affiche la cote
  Cardmarket (le grand marché européen de l'occasion) de produits et de cartes One
  Piece, dans l'onglet « Tendances ».
- **Valorisation des cartes** : un outil d'analyse, utilisé hors du site, estime si
  une carte One Piece est trop chère ou bon marché par rapport à sa rareté, à son
  usage en tournoi et à la popularité de son personnage.
- **Alertes** : le code sait prévenir par e-mail ou Discord quand un produit suivi
  revient en stock. Le système n'est pas encore actif en ligne.

## Où en est le projet

C'est une **alpha privée**. Le site fonctionne, mais :
- les comptes sont créés à la main, il n'y a pas d'inscription publique ;
- les données ne se mettent à jour que lorsque le mainteneur lance un relevé puis
  une publication : il n'y a pas encore de rafraîchissement automatique en ligne ;
- la base en ligne gratuite se met en veille après une semaine sans visite. Il faut
  alors la réveiller depuis la console Supabase.

Prochaines étapes prévues : relevés automatiques sur le serveur, stockage des
images dans le cloud, nom de domaine.

## Les briques techniques

| Partie | Technologie | Rôle |
|---|---|---|
| Scraper | Python | Lit les boutiques, enregistre prix et stock |
| Base de données | SQLite (local), PostgreSQL / Supabase (en ligne) | Stocke produits et historique |
| API | FastAPI, hébergée sur Railway | Sert les données au site, gère les comptes |
| Site web | Next.js, hébergé sur Vercel | Interface utilisateur, en français |

## Pour aller plus loin

- Lancer le projet et les commandes du quotidien : [workflows.md](workflows.md)
- Le détail de chaque script : [scripts.md](scripts.md)
- L'architecture technique : [architecture.md](architecture.md)
