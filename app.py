"""Multi-TCG stock tracker dashboard.

Top-left toggle switches between OPTCG / Naruto Mythos (French) and Pokemon TCG
(multi-language). Run with:   streamlit run app.py
"""
import html
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from scraper import cleanup  # FR-only + price-sanity read-time safety net
from scraper.games import pokemon as pk  # block/series image resolution

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "tcg_stock.sqlite"
IMAGES = ROOT / "images"

OPTCG_GAMES = ["optcg", "naruto_mythos"]
LANG_NAMES = {"fr": "🇫🇷 FR", "en": "🇬🇧 EN", "ja": "🇯🇵 JA", "ko": "🇰🇷 KO", "zh": "🇨🇳 ZH"}

# ----------------------------------------------------------------------------- OPTCG set metadata
SET_PREFIX = {"NRT-KS-ED1": "NRTKSED1", "NRT-SS-ED1": "NRTSSED1"}
SET_NAMES = {
    "OP09": "Les Nouveaux Empereurs", "OP10": "Sang Royal",
    "OP11": "Des Poings Vifs comme l'Éclair", "OP12": "L'Héritage du Maître",
    "OP13": "Successeurs", "OP14": "Les Sept de la Mer d'Azur",
    "OP15": "Aventure sur l'Île de Dieu", "OP16": "L'Heure de la Bataille",
    "OP17": "4th Anniversary",
    "EB02": "Anime 25th Collection", "EB03": "Heroines Edition",
    "PRB01": "The Best", "PRB02": "The Best Vol.2",
    "NRT-KS-ED1": "Konoha Shidō (ED.1)", "NRT-SS-ED1": "Shinobi Shiren Ch.2 (ED.1)",
}
SET_ORDER = ["OP09", "OP10", "OP11", "OP12", "OP13", "OP14", "OP15", "OP16", "OP17",
             "EB02", "EB03", "PRB01", "PRB02", "NRT-KS-ED1", "NRT-SS-ED1"]


def image_for(set_code, kind):
    prefix = SET_PREFIX.get(set_code, set_code)
    suffixes = {"display": ["BB"], "booster": ["SB"], "case": ["CASE", "BB"]}.get(kind, [])
    for suffix in suffixes:
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = IMAGES / f"{prefix}{suffix}.{ext}"
            if p.exists():
                return str(p)
    return None


def change_flag(avail_now, avail_prev, price_now, price_prev):
    """RESTOCK / STOCKOUT / PRICE↓ / PRICE↑ vs the previous snapshot, '' if no
    meaningful change. Mirrors scraper.export_excel.add_flag_and_status."""
    if pd.notna(avail_prev) and avail_now == 1 and avail_prev == 0:
        return "RESTOCK"
    if pd.notna(avail_prev) and avail_now == 0 and avail_prev == 1:
        return "STOCKOUT"
    if pd.notna(price_prev) and pd.notna(price_now):
        d = price_now - price_prev
        if d < -0.5:
            return "PRICE↓"
        if d > 0.5:
            return "PRICE↑"
    return ""


def classify_kind(price, title):
    import re as _re
    t = (title or "").lower()
    if any(k in t for k in ["protection", "plexi", "écrin", "ecrin", "présentoir", "presentoir"]):
        return "accessory"
    has_case_word = bool(_re.search(r"\bcase\b", t)) or "carton" in t
    if price is not None and price >= 1000:
        return "case"
    if has_case_word and "display" in t:
        return "case"
    if has_case_word and ("booster" in t or "blister" in t):
        return "display"
    if any(k in t for k in ["display", "boîte de booster", "boite de booster",
                            "booster box", "boosterbox", "boîte 24", "boite 24",
                            "boîte de 24", "boite de 24", "boîte de 20", "boite de 20"]):
        return "display"
    if "booster" in t and "box" not in t:
        return "booster"
    if price is None:
        return "unknown"
    if price <= 15:
        return "booster"
    if price >= 100:
        return "display"
    return "unknown"


# ----------------------------------------------------------------------------- data access
@st.cache_data(ttl=60)
def load_data(games):
    placeholders = ",".join("?" * len(games))
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query(f"""
            WITH ranked AS (
                SELECT s.product_id, s.observed_at, s.price_eur, s.available, s.stock_remaining,
                       p.platform, p.set_code, p.set_codes, p.series, p.game, p.language,
                       p.kind AS db_kind, p.shop, p.title, p.url,
                       ROW_NUMBER() OVER (PARTITION BY s.product_id ORDER BY s.observed_at DESC) rn
                FROM snapshots s JOIN products p ON p.id = s.product_id
                WHERE p.game IN ({placeholders})
            ),
            latest AS (SELECT * FROM ranked WHERE rn = 1),
            prev   AS (SELECT product_id, price_eur AS price_prev,
                              available AS avail_prev FROM ranked WHERE rn = 2)
            SELECT l.product_id, l.platform, l.set_code, l.set_codes, l.series, l.game,
                   l.language, l.db_kind, l.shop, l.title, l.url, l.price_eur AS price_now,
                   l.available AS avail_now, l.stock_remaining, l.observed_at,
                   p.price_prev, p.avail_prev
            FROM latest l LEFT JOIN prev p USING (product_id)
        """, conn, params=games)
    df["title"] = df["title"].fillna("").apply(html.unescape).str.replace("–", "-", regex=False)
    df["status"] = df["avail_now"].map({1: "In Stock", 0: "Out"}).fillna("Unknown")
    return df


# Block (series) display codes — mirrors games.pokemon.BLOCK_CODES.
BLOCK_CODES = {"me": "ME", "sv": "EV", "swsh": "EB", "sm": "SL", "xy": "XY",
               "bw": "NB", "mc": "MCD", "tcgp": "PKT"}


@st.cache_data(ttl=300)
def pokemon_set_meta():
    """(names{(lang,code):name}, abbr{code:abbr}, series{code:series_id})."""
    names, abbr, series = {}, {}, {}
    with sqlite3.connect(DB) as conn:
        try:
            rows = conn.execute(
                "SELECT language, set_code, name, abbreviation, series "
                "FROM sets WHERE game='pokemon'").fetchall()
        except sqlite3.OperationalError:
            return names, abbr, series
    for l, c, n, ab, ser in rows:
        names[(l, c)] = n
        if ab:
            abbr[c] = ab
        if ser:
            series[c] = ser
    return names, abbr, series


@st.cache_data(ttl=300)
def pokemon_series_names():
    """{series_id: french-or-english name} from the TCGdex series reference."""
    import json
    f = ROOT / "data" / "reference" / "pokemon_series.json"
    if not f.exists():
        return {}
    data = json.loads(f.read_text(encoding="utf-8"))
    out = {}
    for lang in ("en", "fr"):
        out.update(data.get(lang, {}))
    out.update(data.get("fr", {}))  # prefer FR when present
    return out


def fmt_price(p):
    if p is None or pd.isna(p):
        return "—"
    return f"€{p:.2f}"


def _pk_item_table(d, search_key=None):
    """Render the standard Pokemon item table (optionally with an all-column search)."""
    cols = ["language", "series_label", "set_label", "kind", "status", "price_now",
            "shop", "title", "platform", "url"]
    show = d[cols].rename(columns={"series_label": "series", "set_label": "set",
                                   "price_now": "price_€"})
    if search_key:
        q = st.text_input("🔎 Search (all columns)", "", key=search_key,
                          placeholder="e.g. astres radieux, etb, dracaugames, EV05…")
        if q:
            mask = show.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False))
            show = show[mask.any(axis=1)]
    show = show.sort_values(["language", "series", "set", "kind", "price_€"])
    st.caption(f"{len(show)} rows")
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={"url": st.column_config.LinkColumn("link", display_text="open"),
                                "price_€": st.column_config.NumberColumn(format="€%.2f")})


# ----------------------------------------------------------------------------- OPTCG view
def optcg_safety_filter(df):
    """Read-time safety net for OPTCG (FR-only): hide any listing that slipped
    into the DB but is either a non-French edition or has an implausible price
    for its product type (e.g. a 'display' scraped at 7€ from a dead link that
    redirected to a listing page). Keeps the dashboard clean even before the next
    scrape re-writes the bad snapshots. Unknown/zero prices are kept."""
    if df.empty:
        return df
    foreign = df.apply(lambda r: cleanup.is_foreign(r["title"] or "", r["url"] or ""), axis=1)
    bad_price = df.apply(
        lambda r: cleanup.price_out_of_range(r["price_now"], (r["title"] or "").lower()), axis=1)
    return df[~(foreign | bad_price)].copy()


def render_optcg():
    df = optcg_safety_filter(load_data(OPTCG_GAMES))
    df["kind"] = df.apply(lambda r: classify_kind(r["price_now"], r["title"]), axis=1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tracked products", len(df))
    c2.metric("In stock", int((df["avail_now"] == 1).sum()))
    c3.metric("Out of stock", int((df["avail_now"] == 0).sum()))
    c4.metric("Unknown", int(df["avail_now"].isna().sum()))
    last = df["observed_at"].max()
    c5.metric("Last snapshot", last[:16].replace("T", " ") if isinstance(last, str) else "—")

    with st.sidebar:
        st.header("Filters")
        f_sets = st.multiselect("Set", SET_ORDER, default=None)
        f_kind = st.multiselect("Kind", ["display", "booster", "case", "accessory", "unknown"],
                                default=["display", "booster", "case"])
        f_status = st.multiselect("Status", ["In Stock", "Out", "Unknown"], default=["In Stock"])
        f_shop = st.multiselect("Shop", sorted(df["shop"].unique()))
        f_max_price = st.number_input("Max price €", min_value=0.0, value=0.0, step=10.0,
                                      help="0 = no max")
    filt = df.copy()
    if f_sets:   filt = filt[filt["set_code"].isin(f_sets)]
    if f_kind:   filt = filt[filt["kind"].isin(f_kind)]
    if f_status: filt = filt[filt["status"].isin(f_status)]
    if f_shop:   filt = filt[filt["shop"].isin(f_shop)]
    if f_max_price > 0:
        filt = filt[(filt["price_now"].isna()) | (filt["price_now"] <= f_max_price)]

    # MAJ since the previous snapshot (restocks / stockouts / price moves).
    # Built from the full df (not `filt`) so the default "In Stock" status filter
    # doesn't hide stockouts. Uses price_prev/avail_prev from load_data.
    df["flag"] = df.apply(
        lambda r: change_flag(r["avail_now"], r["avail_prev"],
                              r["price_now"], r["price_prev"]), axis=1)
    df["price_change"] = (df["price_now"] - df["price_prev"]).round(2)

    tab_cards, tab_table, tab_changes = st.tabs(
        ["📦 Set cards", "📋 All listings", "🔁 MAJ"])
    with tab_cards:
        st.caption("Cheapest **in-stock** listing per (set × kind).")
        sets_kinds = ([(s, "display") for s in SET_ORDER]
                      + [(s, "booster") for s in SET_ORDER]
                      + [(s, "case") for s in SET_ORDER
                         if len(df[(df["set_code"] == s) & (df["kind"] == "case")]) > 0])
        for i in range(0, len(sets_kinds), 3):
            cols = st.columns(3)
            for j, (sc, k) in enumerate(sets_kinds[i:i + 3]):
                with cols[j]:
                    rows = df[(df["set_code"] == sc) & (df["kind"] == k)]
                    in_stock_rows = rows[rows["avail_now"] == 1].sort_values("price_now")
                    with st.container(border=True):
                        sub_a, sub_b = st.columns([1, 2])
                        img = image_for(sc, k)
                        if img: sub_a.image(img, use_container_width=True)
                        else:   sub_a.markdown("🃏")
                        sub_b.markdown(f"**{sc}** · *{k}*")
                        sub_b.caption(SET_NAMES.get(sc, sc))
                        if len(in_stock_rows):
                            best = in_stock_rows.iloc[0]
                            sub_b.markdown(f"### {fmt_price(best['price_now'])}")
                            sub_b.markdown(f"[{best['shop']}]({best['url']})")
                            sub_b.caption(f"{len(in_stock_rows)} / {len(rows)} in stock")
                        elif len(rows):
                            sub_b.markdown(":grey[**out of stock**]")
                        else:
                            sub_b.markdown(":grey[**no listings**]")
    with tab_table:
        show = filt[["set_code", "kind", "status", "price_now", "stock_remaining",
                     "shop", "title", "platform", "url"]].rename(
            columns={"set_code": "set", "price_now": "price_€", "stock_remaining": "qty_left"})
        show = show.sort_values(["set", "kind", "status", "price_€"])
        st.caption(f"{len(show)} rows")
        st.dataframe(show, use_container_width=True, hide_index=True,
                     column_config={"url": st.column_config.LinkColumn("link", display_text="open"),
                                    "price_€": st.column_config.NumberColumn(format="€%.2f")})

    with tab_changes:
        st.caption("Produits **mis à jour** depuis le snapshot précédent "
                   "(réassort, rupture, variation de prix > 0,50 €).")
        changes = df[df["flag"] != ""].copy()
        flags = st.multiselect("Type de MAJ", ["RESTOCK", "STOCKOUT", "PRICE↓", "PRICE↑"],
                               default=["RESTOCK", "STOCKOUT", "PRICE↓", "PRICE↑"],
                               key="optcg_flags")
        if flags:
            changes = changes[changes["flag"].isin(flags)]
        chg = changes[["flag", "set_code", "kind", "status", "price_prev", "price_now",
                       "price_change", "shop", "title", "platform", "url"]].rename(
            columns={"set_code": "set", "price_prev": "price_prev_€",
                     "price_now": "price_€", "price_change": "Δprice_€"})
        flag_rank = {"RESTOCK": 0, "STOCKOUT": 1, "PRICE↓": 2, "PRICE↑": 3}
        chg = chg.sort_values(by="flag", key=lambda c: c.map(flag_rank)).reset_index(drop=True)
        st.caption(f"{len(chg)} MAJ")
        st.dataframe(chg, use_container_width=True, hide_index=True,
                     column_config={
                         "url": st.column_config.LinkColumn("link", display_text="open"),
                         "price_prev_€": st.column_config.NumberColumn(format="€%.2f"),
                         "price_€": st.column_config.NumberColumn(format="€%.2f"),
                         "Δprice_€": st.column_config.NumberColumn(format="%+.2f")})


# ----------------------------------------------------------------------------- Pokemon view
def render_pokemon():
    df = load_data(["pokemon"])
    if df.empty:
        st.info("No Pokemon products loaded yet. Run `python -m scraper.discover_pokemon` "
                "then `python -m scraper.categorize_pokemon`.")
        return
    names, abbr, series_map = pokemon_set_meta()
    series_names = pokemon_series_names()
    df["series"] = df["series"].fillna("")
    df["set_codes"] = df["set_codes"].fillna("")

    def label_for(lang, code):
        if not code:
            return "❓ unknown set"
        nm = names.get((lang, code)) or names.get(("en", code)) or code
        blk = BLOCK_CODES.get(series_map.get(code, ""), "")
        ab = abbr.get(code, "")
        pre = " · ".join(p for p in (blk, ab) if p)
        return f"{pre} · {nm}" if pre else f"{nm} ({code})"

    def series_label(sid):
        if not sid:
            return "❓ unknown series"
        return f"{BLOCK_CODES.get(sid, sid.upper())} · {series_names.get(sid, sid)}"

    # all sets a product belongs to (multi-set lots), as labels
    def set_list(row):
        codes = [c for c in str(row["set_codes"]).split(";") if c] or [row["set_code"]]
        codes = [c for c in codes if c]
        return codes or [""]   # [""] = unknown set, keeps the row browsable
    df["set_codes_list"] = df.apply(set_list, axis=1)
    df["set_label"] = df.apply(lambda r: label_for(r["language"], r["set_code"]), axis=1)
    df["set_labels_all"] = df.apply(
        lambda r: [label_for(r["language"], c) for c in r["set_codes_list"]] or [r["set_label"]], axis=1)
    df["series_label"] = df["series"].apply(series_label)
    df["kind"] = df["db_kind"].fillna("unknown")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Listings", len(df))
    c2.metric("In stock", int((df["avail_now"] == 1).sum()))
    c3.metric("Set identified", f"{int((df['set_code'] != '').sum())}/{len(df)}")
    c4.metric("Multi-set lots", int((df['set_codes_list'].apply(len) > 1).sum()))
    c5.metric("Shops", df["shop"].nunique())

    all_set_labels = sorted({lbl for lst in df["set_labels_all"] for lbl in lst if "unknown" not in lbl})
    with st.sidebar:
        st.header("Pokemon filters")
        langs = [l for l in LANG_NAMES if l in set(df["language"])]
        f_lang = st.multiselect("Language", langs, default=langs,
                                format_func=lambda l: LANG_NAMES.get(l, l))
        f_block = st.multiselect("Block / series", sorted(df["series_label"].unique()))
        f_set = st.multiselect("Set", all_set_labels,
                               help="A multi-set lot appears under each of its sets.")
        f_kind = st.multiselect("Kind", sorted(df["kind"].unique()),
                                default=sorted(df["kind"].unique()))
        f_status = st.multiselect("Status", ["In Stock", "Out", "Unknown"], default=["In Stock"])
        f_shop = st.multiselect("Shop", sorted(df["shop"].unique()))
        only_known = st.checkbox("Only identified sets", value=False)
        f_max_price = st.number_input("Max price €", min_value=0.0, value=0.0, step=10.0)

    filt = df.copy()
    if f_lang:     filt = filt[filt["language"].isin(f_lang)]
    if f_block:    filt = filt[filt["series_label"].isin(f_block)]
    if f_set:      filt = filt[filt["set_labels_all"].apply(lambda L: any(s in f_set for s in L))]
    if f_kind:     filt = filt[filt["kind"].isin(f_kind)]
    if f_status:   filt = filt[filt["status"].isin(f_status)]
    if f_shop:     filt = filt[filt["shop"].isin(f_shop)]
    if only_known: filt = filt[filt["set_code"] != ""]
    if f_max_price > 0:
        filt = filt[(filt["price_now"].isna()) | (filt["price_now"] <= f_max_price)]

    tab_browse, tab_cards, tab_table = st.tabs(
        ["🗂️ Browse", f"🃏 Items ({len(filt)})", "📋 Table"])

    # ---- Browse: Block -> Set -> items drill-down, with block/series images.
    #      Blocks keyed by series_id, sets by set_code (multi-set lots appear under each).
    with tab_browse:
        exb = filt.explode("set_codes_list").copy()
        exb["code2"] = exb["set_codes_list"].fillna("")
        exb["sid2"] = exb["code2"].apply(lambda c: series_map.get(c, "") if c else "")

        sel_block = st.session_state.get("pk_block")   # series_id ("" = unknown)
        sel_set = st.session_state.get("pk_set")       # set_code   ("" = unknown)

        def _img_grid(items, state_key, img_fn, label_fn):
            """items: list of (code, count). Renders image (if any) + a button per cell."""
            PER = 4
            for i in range(0, len(items), PER):
                cols = st.columns(PER)
                for j, (code, n) in enumerate(items[i:i + PER]):
                    with cols[j]:
                        img = img_fn(code) if code else None
                        if img and Path(img).exists():
                            st.image(img, use_container_width=True)
                        if st.button(f"{label_fn(code)} · {n}", key=f"{state_key}_{i+j}",
                                     use_container_width=True):
                            st.session_state[state_key] = code
                            if state_key == "pk_block":
                                st.session_state["pk_set"] = None
                            st.rerun()

        if sel_block is not None and sel_set is not None:
            if st.button("← Retour aux séries"):
                st.session_state["pk_set"] = None
                st.rerun()
            img = pk.series_image(sel_set) if sel_set else None
            h1, h2 = st.columns([1, 6])
            if img and Path(img).exists():
                h1.image(img, width=120)
            set_name = label_for("fr", sel_set) if sel_set else "❓ série inconnue"
            h2.markdown(f"### {series_label(sel_block)}\n#### {set_name}")
            sub = exb[(exb["sid2"] == sel_block) & (exb["code2"] == sel_set)]
            _pk_item_table(sub.drop_duplicates("product_id"))
        elif sel_block is not None:
            if st.button("← Retour aux blocs"):
                st.session_state["pk_block"] = None
                st.rerun()
            st.markdown(f"### {series_label(sel_block)} — choisissez une série")
            sets = (exb[exb["sid2"] == sel_block].groupby("code2")["product_id"]
                    .nunique().sort_values(ascending=False))
            # Tile label = official code (PRE, CRI…); the name lives in the image.
            _img_grid(list(sets.items()), "pk_set", pk.series_image,
                      lambda c: (pk.abbreviation_of(c) or c) if c else "❓ inconnue")
        else:
            st.caption("Choisissez un **bloc**, puis une **série**.")
            blocks = exb.groupby("sid2")["product_id"].nunique().sort_values(ascending=False)
            _img_grid(list(blocks.items()), "pk_block", pk.block_image,
                      lambda c: series_label(c) if c else "❓ bloc inconnu")

    with tab_cards:
        st.caption("Images not ready — each card shows **name + set + language** as a text "
                   "placeholder. This is the raw auto-categorized list; curate later.")
        rows = filt.sort_values(["set_label", "kind", "price_now"]).reset_index(drop=True)
        PER_ROW = 3
        for i in range(0, len(rows), PER_ROW):
            cols = st.columns(PER_ROW)
            for j in range(PER_ROW):
                if i + j >= len(rows):
                    break
                r = rows.iloc[i + j]
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(
                            f"<div style='background:#F2F2F2;border-radius:6px;padding:10px;"
                            f"font-size:0.85em;line-height:1.35'>"
                            f"🃏 <b>{html.escape(r['title'][:80])}</b><br>"
                            f"📦 {html.escape(str(r['set_label']))}<br>"
                            f"🌐 {LANG_NAMES.get(r['language'], r['language'])} · {r['kind']}"
                            f"</div>", unsafe_allow_html=True)
                        badge = {"In Stock": "🟢", "Out": "🔴", "Unknown": "⚪"}.get(r["status"], "")
                        st.markdown(f"### {fmt_price(r['price_now'])}  {badge}")
                        st.markdown(f"[{r['shop']}]({r['url']})")

    with tab_table:
        _pk_item_table(filt, search_key="pk_table_search")


# ----------------------------------------------------------------------------- page
st.set_page_config(page_title="TCG Tracker", layout="wide", page_icon="🎴")

top_l, top_r = st.columns([1, 4])
with top_l:
    game = st.radio("TCG", ["One Piece / Naruto", "Pokémon"], label_visibility="collapsed")
with top_r:
    st.title("🎴 Pokémon — Stock Tracker" if game == "Pokémon"
             else "🎴 OPTCG / Naruto Mythos — Stock Tracker")

if game == "Pokémon":
    render_pokemon()
else:
    render_optcg()

st.divider()
st.caption(f"DB: {DB.name}")
