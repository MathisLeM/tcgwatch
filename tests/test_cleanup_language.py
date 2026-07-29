"""Language classification for OPTCG (FR-only): `cleanup.is_foreign`.

Covers the category / breadcrumb / "VO" signals added so that JP/EN editions
whose language is absent from the title are still recognised and dropped — and,
just as important, that genuinely French products are NOT mis-flagged.
"""
import pytest
from scraper import cleanup


# (title, url, extra) tuples that must be detected as foreign (non-French).
FOREIGN = [
    # troll2jeux: "VO" = version originale = English (only signal is the title).
    ("One Piece : OP16 THE TIME OF BATTLE display VO",
     "https://troll2jeux.com/one-piece/10063077-...-display-vo.html", ""),
    ("One Piece Royal Blood OP10 Booster VO (blister)", "", ""),
    ("Some display", "", "version originale"),
    # lerepairetcg: language only in the breadcrumb / product category.
    ("Display One Piece EB-02 Anime 25th Collection",
     "https://lerepairetcg.com/?product=display-one-piece-eb-02-anime-25th-collection",
     "one piece produits op japonais"),
    # jmcards: "Japonais" category (title carries an English set name only).
    ("One Piece Trading CG - Display OP-10 Royal Blood", "", "Japonais One Piece"),
    ("Display 24 booster One piece OP-13 Inherited Will", "", "Japonais One Piece"),
    # bare tokens in the category/description
    ("One Piece OP-15 Adventure on Kami's Island", "", "One Piece (JAP)"),
    ("One Piece OP-15", "", "English"),
    # pre-existing behaviour still works
    ("One Piece OP-11 (JP)", "", ""),
    ("One Piece booster english", "", ""),
    # carteonepiece / lootboxjeux: English import tagged "ENG" in the title...
    ("OP10 Display Box - 24 boosters - Royal Blood ENG", "", ""),
    ("One Piece - OP15 - Adventure on Kami's Island - Booster ENG",
     "https://lootboxjeux.fr/products/one-piece-op15-adventure-on-kamis-island-booster-eng", ""),
    # ...or only in the URL slug (title truncated), incl. a mid-slug tag.
    ("OPCG - EB-02 Anime 25th",
     "https://www.tales-of-games.fr/jcc-one-piece/31191-one-piece-eb-02-anime-25th-collection-booster-eng-0810059788756.html",
     ""),
    ("OP12 Display Box", "https://carteonepiece.fr/products/op12-display-box-24-boosters-legacy-of-the-master-eng", ""),
]

# Genuinely French products that must be KEPT (the false-positive guards).
FRENCH = [
    ("One Piece OP10 : Sang royal Display de Boosters VF", "", ""),
    ("Display One Piece OP-10 Royal Bloodline", "", "one piece"),
    ("One Piece - Display de 24 boosters OP-09 : Les Nouveaux Empereurs", "",
     "Francais One Piece"),
    ("Booster OP13 One Piece Successeurs Version francaise", "", ""),
    # "en" is a French preposition, must not trip the EN tag (case-sensitive).
    ("Display One Piece en blister OP-13", "", "one piece"),
    ("One Piece OP-12 Volume special", "", ""),
    # French shop whose category is just the product type / generic TCG label.
    ("Display EB-02 Anime 25th Collection - Francais", "", "One Piece TCG Scelle"),
    ("One Piece TCG: Case scellee 12 display OP10 FRANCAIS", "",
     "Display Jeux de cartes TCG One Piece TCG"),
    # "eng" must be a standalone slug token — not a substring of a French word.
    ("Booster One Piece rangement OP13", "https://shop.fr/produits/booster-rangement-op13", ""),
    # lowercase "eng" inside the title (not an uppercase tag) must not trip it.
    ("One Piece display strengthened OP12", "", ""),
]


@pytest.mark.parametrize("title,url,extra", FOREIGN)
def test_foreign_detected(title, url, extra):
    assert cleanup.is_foreign(title, url, extra) is True


@pytest.mark.parametrize("title,url,extra", FRENCH)
def test_french_kept(title, url, extra):
    assert cleanup.is_foreign(title, url, extra) is False
