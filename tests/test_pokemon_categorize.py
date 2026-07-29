"""Offline tests for Pokemon categorization (set / series / kind / sealed gate).

Uses real, representative shop titles. No network, no DB — purely exercises
`scraper.games.pokemon` against the bundled TCGdex reference JSON. Run: `pytest`.
"""
import pytest

from scraper.games import pokemon


# --------------------------------------------------------------------------- #
# Set extraction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title, lang, expected", [
    # FR/EN "151" must resolve to the specific half-set sv03.5, NOT the block
    # base sv01 ("Écarlate et Violet"). This was the main FR mis-categorization.
    ("Booster - Écarlate et Violet : 151 [EV3.5] - FR", "fr", "sv03.5"),
    ("Coffret Dresseur Élite ETB Pokémon EV 3.5 – 151 (AN)", "fr", "sv03.5"),
    ("Pokémon 151 Booster EN", "en", "sv03.5"),
    ("Pokemon 151 Elite Trainer Box EN", "en", "sv03.5"),
    # JA "151" uses the Japanese numbering SV2a.
    ("Pokemon Card 151 sv2a Booster Box - Japanese", "ja", "SV2a"),
    # French community codes (EV##/EB##), with and without a half-set decimal.
    ("Booster Pokémon EV01 Écarlate et Violet", "fr", "sv01"),
    ("Display Pokémon EB12 Tempête Argentée", "fr", "swsh12"),
    # Official set abbreviations (PRE / OBF / CRI ...).
    ("Display Pokémon PRE Étincelles Déferlantes", "fr", "sv08.5"),
    ("Booster Pokémon OBF Flammes Obsidiennes EN", "en", "sv03"),
    # Japanese set codes with letter suffixes — validated against the JA reference.
    ("Booster Battle Partners - SV9 - Japonais", "ja", "SV9"),
    ("Booster Cyber Judge - SV5M - Japonais", "ja", "SV5M"),
    ("Booster Heat Wave Arena - SV9A - Japonais", "ja", "SV9a"),
    ("Booster Paradigm Trigger - S12 - Japonais", "ja", "S12"),
    ("Booster Inferno X – M2 – Japonais", "ja", "M2"),
])
def test_extract_set(title, lang, expected):
    assert pokemon.extract_set(title, "", lang) == expected


def test_jp_code_not_used_for_french_titles():
    # A French title with an "SV9"-like token must not silently grab a JA code;
    # JP code matching is scoped to CJK listings.
    assert pokemon.extract_set("Booster Pokémon Écarlate et Violet SV9", "", "fr") != "SV9"


def test_jp_code_validated_against_language():
    # KO/ZH keep their own (language, set_code) identity; a JA-only code that does
    # not exist for the listing language is not borrowed.
    code = pokemon.extract_set("부스터 SV2a 151", "", "ko")
    assert code in pokemon.valid_sets("ko") or code == ""


def test_extract_set_unknown_old_set_returns_blank():
    # Pre-2020 sets aren't in the reference; we must return '' rather than guess.
    assert pokemon.extract_set("Booster GYM Leaders Stadium 1998 Japonais", "", "ja") == ""


# --------------------------------------------------------------------------- #
# Series / block normalization (JA/KO/ZH raw ids -> real block names)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("series_id, fr_name", [
    ("SV", "Écarlate et Violet"),   # JA uppercase era id -> sv block
    ("sv", "Écarlate et Violet"),
    ("S", "Épée et Bouclier"),      # JA Sword & Shield era -> swsh block
    ("M", "Méga-Évolution"),        # JA Mega era -> me block
])
def test_series_name_normalizes_jp_ids(series_id, fr_name):
    assert pokemon.series_name(series_id, "fr") == fr_name


@pytest.mark.parametrize("series_id, code", [
    ("SV", "EV"), ("S", "EB"), ("M", "ME"), ("sv", "EV"),
])
def test_block_code_normalizes_jp_ids(series_id, code):
    assert pokemon.block_code(series_id) == code


def test_block_image_resolves_for_jp_series():
    # The 3 curated block images (sv/swsh/me) must resolve from a JA series id too.
    assert pokemon.block_image("SV") is not None
    assert pokemon.block_image("S") is not None
    assert pokemon.block_image("M") is not None


def test_extract_series_from_jp_set_code():
    s = pokemon.extract_set("Booster Battle Partners - SV9 - Japonais", "", "ja")
    series = pokemon.extract_series("Booster Battle Partners - SV9", "", "ja", "", s)
    assert pokemon.series_name(series, "fr") == "Écarlate et Violet"


# --------------------------------------------------------------------------- #
# Kind classification — JP "BOX" -> display
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title, lang", [
    ("Shiny Treasure ex BOX JP", "ja"),
    ("Terastal Festival ex BOX", "ja"),
    ("Pokemon Card 151 sv2a BOX - Japanese", "ja"),
    ("포켓몬 카드 151 박스", "ko"),
])
def test_jp_bare_box_is_display(title, lang):
    assert pokemon.classify_kind(title, language=lang) == "display"


def test_explicit_booster_box_is_display_any_language():
    assert pokemon.classify_kind("Mega Dream ex Booster Box JP", language="ja") == "display"


@pytest.mark.parametrize("title", [
    "Coffret Premium Trainer Box Pokémon FR",   # not a display
    "Pokémon Tin Box Dracaufeu",                 # coffret, not display
])
def test_french_bare_box_does_not_become_display(title):
    # The bare-'box' display rule is CJK-only; FR/EN 'box' stays ambiguous/specific.
    assert pokemon.classify_kind(title, language="fr") != "display"


# --------------------------------------------------------------------------- #
# Sealed gate — relaxation must not reintroduce singles / goodies
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title, lang", [
    ("Shiny Treasure ex BOX JP", "ja"),
    ("Terastal Festival ex BOX", "ja"),
])
def test_is_sealed_accepts_jp_box(title, lang):
    assert pokemon.is_sealed(title, language=lang) is True


@pytest.mark.parametrize("title, lang", [
    ("Carte Pikachu 025/165 PSA 10 BOX", "ja"),   # graded single, has 'box'
    ("Deck Box Pokémon vide", "ja"),              # accessory
    ("Sleeve Pokémon box", "ja"),                 # accessory
    ("カードローダー 単品 BOX", "ja"),             # JA loose single + box
    ("포켓몬 낱장 박스", "ko"),                    # KO loose card + box
])
def test_is_sealed_still_drops_singles_and_goodies_with_box(title, lang):
    assert pokemon.is_sealed(title, language=lang) is False


# --------------------------------------------------------------------------- #
# Keyword enrichment — promo-inclusion vs promo-single, decks, pins, decoded
# entities. All titles are real shop listings from the raw Pokemon scrape.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title, lang", [
    # A sealed display/booster/pack that merely *includes* a promo card must NOT
    # be dropped as a single — this was the main FR sealed false-negative.
    ("Display de 36 boosters Méga-Évolution - Pokémon FR (avec carte promo)", "fr"),
    ("Pokémon Méga-Évolution - ME01 - Display de 36 Boosters + Carte Promo", "fr"),
    ("Tripack Pokémon ME01 Méga-Évolution – 3 boosters + carte promo (FR)", "fr"),
    ("Pokémon - Pack Promo 2 Boosters (1 Carte Promo) (FR)", "fr"),
    ("Display Pokémon SV9 Battle Partners sans carte promo – Japonais", "ja"),
])
def test_sealed_with_included_promo_is_kept(title, lang):
    assert pokemon.is_sealed(title, language=lang) is True


@pytest.mark.parametrize("title, lang", [
    # A loose promo card (no sealed-kind word) must still be dropped.
    ("Carte Promo Hôtel Au paradis des Pokémon WCS 2025", "fr"),
    ("Axoloto de Paldea – SV-P 193 – Carte Promo Pokémon Japonais", "ja"),
    ("Carte Promo Pokémon Japonaise – Victini 271/SV-P (Scellée)", "ja"),
])
def test_loose_promo_single_is_dropped(title, lang):
    assert pokemon.is_sealed(title, language=lang) is False


@pytest.mark.parametrize("title, lang", [
    ("Pokémon : Bundle Deck Lougaroc/Corvaillus", "fr"),
    ("Deck à thème Pokémon Épée et Bouclier - Gorythmic FR (Blister)", "fr"),
    ("Deck avec Booster - Pokemon - Triomphe - Garde Royale - Scellé - Français", "fr"),
    ("Lycanroc VS Corviknight V Battle Deck Bundle EN", "en"),
    ("Pokémon - Deck Build Box Stellar Miracle | JP", "ja"),
    ("Coffret Pokémon Épée et Bouclier Starter VMAX Japonnais", "ja"),
])
def test_preconstructed_decks_are_dropped(title, lang):
    assert pokemon.is_sealed(title, language=lang) is False


@pytest.mark.parametrize("title, lang", [
    # 'pin's' goodies, including HTML-entity / typographic-apostrophe variants.
    ("Coffret Pin's Deluxe Pokémon ME2.5 Héros Transcendants", "fr"),
    ("Coffret Pin’s Deluxe Héros Transcendants ME2.5 - Pokemon", "fr"),
    ("Pokémon &#8211; Coffret Pin&rsquo;s Deluxe Premiers Partenaires", "fr"),
    ("Pokemon ME02.5 : Héros Transcendants - Deluxe pin box (5 boosters + pins)", "fr"),
    # Empty boxes / card holders / deck cases sold as storage.
    ("Pokémon - Boite Vide ETB - EV09 Ecarlate et Violet - Deck case", "fr"),
    ("Coffret - Porte-carte Starter de Galar CS1.5DF2", "fr"),
])
def test_pins_and_empty_boxes_are_dropped(title, lang):
    assert pokemon.is_sealed(title, language=lang) is False


def test_html_entities_decoded_before_keyword_match():
    # `_norm` unescapes entities + folds curly punctuation, so a goodie keyword
    # hidden behind `&rsquo;` / `&#8211;` is still caught.
    assert "pin's" in pokemon._norm("Coffret Pin&rsquo;s Deluxe")
    assert "pin's" in pokemon._norm("Coffret Pin’s Deluxe")
    assert "-" in pokemon._norm("Méga&#8211;Évolution")


def test_real_sealed_displays_still_pass():
    # Sanity: ordinary sealed product is unaffected by the new drops.
    assert pokemon.is_sealed("Display Pokémon EB12 Tempête Argentée", language="fr")
    assert pokemon.is_sealed("Coffret Dresseur Élite ETB Pokémon EV3.5 – 151", language="fr")
    assert pokemon.is_sealed("Booster Pokémon Écarlate et Violet", language="fr")


def test_trusted_desc_shop_relaxation_is_off_by_default():
    # An uninformative title is NOT promoted by a description for an unknown shop.
    title = "Nouveau produit Pokémon Étincelles Déferlantes"
    desc = "Display de 36 boosters scellé"
    assert pokemon.is_sealed(title, desc, language="fr", shop="random-shop.fr") is False


# --------------------------------------------------------------------------- #
# Cross-game contamination — other TCGs cross-listed in a Pokemon collection
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title", [
    "Lorcana - Wilds Unknown - Case 4 Displays (24) - EN",
    "Yu-Gi-Oh! Display de 10 boosters World Championship 2025",
    "Display Weiss schwarz uma musume english",
    "Display shadowverse evolve BP17 Convergent Destinies EN",
    "Booster Dragon Ball Super Card Game Fusion World",
    "Digimon Card Game Booster Display BT21",
])
def test_other_tcg_products_are_dropped(title):
    assert pokemon.is_other_tcg(title) is True
    assert pokemon.is_sealed(title) is False


@pytest.mark.parametrize("title", [
    "Pokémon - Protection en plexiglass pour display française/anglaise",
    "Pokémon - Protection en plexiglass pour bundle scellé (x10 bundles)",
    "Boitier de protection pour ETB Pokémon",
])
def test_plexiglass_protectors_are_dropped(title):
    assert pokemon.is_sealed(title) is False


def test_pokemon_title_not_flagged_as_other_tcg():
    # A normal Pokemon title must never trip the cross-game guard.
    assert pokemon.is_other_tcg("Display Pokémon Écarlate et Violet 151") is False
    assert pokemon.is_other_tcg("Booster Pokémon Méga-Évolution ME01") is False


# --------------------------------------------------------------------------- #
# Article-type labels & block taxonomy (block > set > type navigation)
# --------------------------------------------------------------------------- #
def test_kind_labels_are_localised():
    assert "Display" in pokemon.kind_label("display", "fr")
    assert pokemon.kind_label("etb", "en") == "Elite Trainer Box (ETB)"
    assert pokemon.kind_label("nonsense") == pokemon.KIND_LABELS["unknown"]["fr"]


@pytest.mark.parametrize("set_code, block", [
    ("sv03.5", "sv"), ("swsh12", "swsh"), ("me01", "me"), ("SV9", "sv"),
    ("S12", "swsh"), ("M2", "me"),
])
def test_set_block_resolves_canonical_block(set_code, block):
    assert pokemon.set_block(set_code) == block


def test_sets_in_block_merges_languages_and_orders_by_release():
    me = pokemon.sets_in_block("me")
    assert "me01" in me            # international code
    assert any(c.startswith("M") for c in me)   # JP code in same block
    # de-duplicated
    assert len(me) == len(set(me))


def test_trusted_desc_shop_relaxation_promotes_when_whitelisted():
    title = "Nouveau produit Pokémon Étincelles Déferlantes"
    desc = "Display de 36 boosters scellé"
    pokemon.TRUSTED_DESC_SHOPS.add("trusted-shop.fr")
    try:
        assert pokemon.is_sealed(title, desc, language="fr", shop="trusted-shop.fr") is True
        # ...but a goodie description is still rejected even for a trusted shop.
        assert pokemon.is_sealed("Goodie Pokémon", "Sleeve protège carte",
                                 language="fr", shop="trusted-shop.fr") is False
    finally:
        pokemon.TRUSTED_DESC_SHOPS.discard("trusted-shop.fr")
