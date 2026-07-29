"""
Catalogue produits cible pour le POC "Île-de-France".

Perimetre demande : boosters / double packs / blisters des sets
EB03, OP13, OP14, OP15, OP16, PRB02 (One Piece Card Game).

Chaque entree = un "produit logique" (set + variante). La cle par enseigne
vaut None quand le produit n'a pas ete trouve chez cette enseigne au moment
du catalogage (14/07/2026) - c'est un etat reel du marche, pas un bug : toutes
les enseignes ne vendent pas toutes les references.

  - fnac       : "prid" (identifiant produit Fnac, utilisable dans /a<prid>)
  - kingjouet  : "uuid" (identifiant produit King Jouet, requis par l'API
                 stock ; le "ref" numerique sert seulement a batir l'URL)
  - cultura    : "sku" (= identifiant produit Cultura)
"""

PRODUCTS = [
    {
        "set_code": "EB03",
        "variant": "Blister",
        "name": "One Piece EB03 - Heroines Edition (Booster Blister)",
        "fnac": {"prid": "22385246"},
        "kingjouet": {"uuid": "f7abc2d9-9bc6-46f6-abde-de05f721494e", "ref": "1007701"},
        "cultura": {"sku": None},
    },
    {
        "set_code": "OP13",
        "variant": "Blister",
        "name": "One Piece OP13 - Les Successeurs (Booster Blister)",
        "fnac": {"prid": "21829267"},
        "kingjouet": {"uuid": None, "ref": None},
        "cultura": {"sku": "12462175"},
    },
    {
        "set_code": "OP14",
        "variant": "Blister",
        "name": "One Piece OP14 - Les Sept de la Mer d'Azur (Booster Blister)",
        "fnac": {"prid": "22385245"},
        "kingjouet": {"uuid": "c425ba07-65aa-4822-be47-6ef21848d7ed", "ref": "1007699"},
        "cultura": {"sku": "12777658"},
    },
    {
        "set_code": "OP14",
        "variant": "Double Pack",
        "name": "One Piece OP14 - Les Sept de la Mer d'Azur (Double Pack)",
        "fnac": {"prid": "22385257"},
        "kingjouet": {"uuid": "5544f9d4-4cd6-4a8b-9ba5-727aca97e1a3", "ref": "1007700"},
        "cultura": {"sku": "12777653"},
    },
    {
        "set_code": "OP15",
        "variant": "Blister",
        "name": "One Piece OP15 - Aventure sur l'Île de Dieu (Booster Blister)",
        "fnac": {"prid": "22530904"},
        "kingjouet": {"uuid": "36435926-1047-43db-89a8-a3e4e4513188", "ref": "1028819"},
        "cultura": {"sku": "12777651"},
    },
    {
        "set_code": "OP15",
        "variant": "Double Pack",
        "name": "One Piece OP15 - Aventure sur l'Île de Dieu (Double Pack)",
        "fnac": {"prid": "22530901"},
        "kingjouet": {"uuid": "2b714523-abd8-4cd1-95a2-a85571b4dec3", "ref": "1028820"},
        "cultura": {"sku": "12777647"},
    },
    {
        "set_code": "OP16",
        "variant": "Blister",
        "name": "One Piece OP16 - L'heure de la Bataille Décisive (Booster Blister)",
        "fnac": {"prid": "23123796"},
        "kingjouet": {"uuid": "a7d3e2fa-83d8-46d2-89ff-82ffa77c4ade", "ref": "1034198"},
        "cultura": {"sku": "13080126"},
    },
    {
        "set_code": "OP16",
        "variant": "Double Pack",
        "name": "One Piece OP16 - L'heure de la Bataille Décisive (Double Pack)",
        "fnac": {"prid": "23123806"},
        "kingjouet": {"uuid": "54ad08b1-22f6-41da-b907-635fe887a95c", "ref": "1034904"},
        "cultura": {"sku": None},
    },
    {
        "set_code": "PRB02",
        "variant": "Blister",
        "name": "One Piece PRB02 - The Best Vol. 2 (Premium Booster Blister)",
        "fnac": {"prid": None},
        "kingjouet": {"uuid": "ae4829b3-23ef-4759-8388-18d00c27a0ef", "ref": "993042"},
        "cultura": {"sku": "12369076"},
    },
]

SET_CODES = ["EB03", "OP13", "OP14", "OP15", "OP16", "PRB02"]

# ---------------------------------------------------------------------------
# Annuaire statique des magasins Cultura en Île-de-France (17 magasins).
# Recupere en UN SEUL appel GraphQL (stores(limit:200)) puis filtre sur les
# codes postaux 75/77/78/91/92/93/94/95, le 14/07/2026. A rafraichir de temps
# en temps (nouvelles ouvertures/fermetures) en relancant la meme requete.
# ---------------------------------------------------------------------------
CULTURA_IDF_STORES = [
    {"id": 232, "seller_code": "CB2", "name": "Cultura Bay 2-Collégien", "postcode": "77090", "city": "COLLEGIEN", "lat": 48.8377, "lon": 2.66141},
    {"id": 304, "seller_code": "CBE", "name": "Cultura Belle Epine", "postcode": "94320", "city": "THIAIS", "lat": 48.7566, "lon": 2.37199},
    {"id": 40, "seller_code": "CCE", "name": "Cultura Carré Sénart", "postcode": "77127", "city": "LIEUSAINT", "lat": 48.6185, "lon": 2.54524},
    {"id": 366, "seller_code": "CGY", "name": "Cultura Cergy", "postcode": "95800", "city": "CERGY", "lat": 49.0538, "lon": 2.0543},
    {"id": 52, "seller_code": "CCS", "name": "Cultura Claye Souilly", "postcode": "77410", "city": "CLAYE SOUILLY", "lat": 48.9464, "lon": 2.66937},
    {"id": 61, "seller_code": "CFR", "name": "Cultura Franconville", "postcode": "95130", "city": "FRANCONVILLE LA GARENNE", "lat": 48.9891, "lon": 2.20912},
    {"id": 64, "seller_code": "CGE", "name": "Cultura Gennevilliers", "postcode": "92230", "city": "GENNEVILLIERS", "lat": 48.9338, "lon": 2.31841},
    {"id": 328, "seller_code": "CIS", "name": "Cultura Issy-Les-Moulineaux", "postcode": "92130", "city": "ISSY LES MOULINEAUX", "lat": 48.826405, "lon": 2.275005},
    {"id": 358, "seller_code": "CIA", "name": "Cultura L'Isle-Adam", "postcode": "95260", "city": "MOURS", "lat": 49.127174, "lon": 2.249485},
    {"id": 184, "seller_code": "C4T", "name": "Cultura La Défense", "postcode": "92092", "city": "PUTEAUX", "lat": 48.8929, "lon": 2.23692},
    {"id": 334, "seller_code": "CMP", "name": "Cultura Maurepas", "postcode": "78310", "city": "Maurepas", "lat": 48.759354, "lon": 1.917465},
    {"id": 319, "seller_code": "CMV", "name": "Cultura Montevrain", "postcode": "77144", "city": "MONTEVRAIN", "lat": 48.853176, "lon": 2.754679},
    {"id": 175, "seller_code": "COR", "name": "Cultura Pince Vent", "postcode": "94510", "city": "LA QUEUE EN BRIE", "lat": 48.7924, "lon": 2.55775},
    {"id": 112, "seller_code": "CPL", "name": "Cultura Plaisir / Les Clayes-sous-Bois", "postcode": "78340", "city": "LES CLAYES SOUS BOIS", "lat": 48.8287, "lon": 1.97117},
    {"id": 238, "seller_code": "CRB", "name": "Cultura Rambouillet", "postcode": "78120", "city": "RAMBOUILLET", "lat": 48.6257, "lon": 1.82624},
    {"id": 338, "seller_code": "CG3", "name": "Cultura Sainte Geneviève Des Bois", "postcode": "91700", "city": "ST GENEVIEVE des BOIS", "lat": 48.62133, "lon": 2.348879},
    {"id": 187, "seller_code": "CVS", "name": "Cultura Villennes Sur Seine / Orgeval", "postcode": "78670", "city": "VILLENNES SUR SEINE", "lat": 48.9285, "lon": 1.986},
]

IDF_POSTCODE_PREFIXES = ("75", "77", "78", "91", "92", "93", "94", "95")


def is_idf_postcode(postcode: str) -> bool:
    return bool(postcode) and postcode[:2] in IDF_POSTCODE_PREFIXES
