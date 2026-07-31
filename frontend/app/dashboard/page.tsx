"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Protected from "@/components/Protected";
import Icon from "@/components/Icons";
import {
  addFavorite,
  deleteFavorite,
  Facets,
  fetchFacets,
  fetchProductHistory,
  fetchProducts,
  fetchSets,
  Favorite,
  imageUrl,
  listFavorites,
  ProductListing,
  SetRef,
} from "@/lib/api";

const POKEMON = ["pokemon"];
const OPTCG = ["optcg", "naruto_mythos"];
const BLOCK_CODES: Record<string, string> = {
  me: "ME", sv: "EV", swsh: "EB", sm: "SL", xy: "XY", bw: "NB", mc: "MCD",
};
const PAGE = 50;
const HISTORY_DAYS = 30;

const ORDERS = [
  { value: "default", label: "Sets les plus récents" },
  { value: "set_old", label: "Sets les plus anciens" },
  { value: "block", label: "Par bloc / série" },
  { value: "price_asc", label: "Prix croissant" },
  { value: "price_desc", label: "Prix décroissant" },
  { value: "recent", label: "Derniers scans" },
];

const STATUS: Record<string, { label: string; className: string }> = {
  "In Stock": { label: "En stock", className: "bg-ok-soft text-ok" },
  Out: { label: "Épuisé", className: "bg-[rgb(229_98_108_/_0.12)] text-[#E5626C]" },
  Unknown: { label: "Inconnu", className: "bg-panel-2 text-dim" },
};

const SELECT =
  "rounded-[10px] bg-panel border border-line-strong px-3 py-2.5 text-[13px] text-ink cursor-pointer " +
  "outline-none focus:border-accent transition-colors";

function fmtPrice(p: number | null) {
  return p == null ? "—" : `${p.toFixed(2).replace(".", ",")} €`;
}

/** Polyline for a 72×22 sparkline, normalised over the series' own min/max. */
function sparkPoints(hist: number[]): string {
  if (hist.length < 2) return "";
  const min = Math.min(...hist);
  const max = Math.max(...hist);
  const span = max - min;
  return hist
    .map((v, i) => {
      const x = i * (68 / (hist.length - 1)) + 2;
      // A price that never moved has no range to normalise against — draw it
      // mid-box, otherwise it would sit on the floor and read as "at its lowest".
      const y = span === 0 ? 11 : 19 - ((v - min) / span) * 16;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

/** Change since the start of the window, ignored below 1% so noise stays quiet. */
function priceDelta(hist: number[], price: number | null) {
  if (hist.length < 2 || price == null || !hist[0]) return null;
  const pct = ((price - hist[0]) / hist[0]) * 100;
  if (Math.abs(pct) < 1) return null;
  return {
    label: `${pct > 0 ? "+" : "−"}${Math.abs(pct).toFixed(0)} %`,
    down: pct < 0,
  };
}

/** "il y a 18 min" from a naive ISO timestamp written by the scraper. */
function sinceLabel(iso: string | null): string | null {
  if (!iso) return null;
  const ms = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(ms)) return null;
  const min = Math.floor(ms / 60000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.floor(h / 24);
  return `il y a ${d} j`;
}

function StatusPill({ s, small }: { s: string; small?: boolean }) {
  const cfg = STATUS[s] ?? STATUS.Unknown;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-[3px] rounded-full font-medium
                  ${small ? "text-[11.5px]" : "text-xs"} ${cfg.className}`}
    >
      <span className="w-[5px] h-[5px] rounded-full bg-current" />
      {cfg.label}
    </span>
  );
}

function Sparkline({ hist, down, width = 72 }: { hist: number[]; down: boolean | null; width?: number }) {
  const points = sparkPoints(hist);
  if (!points) return null;
  const stroke = down == null ? "var(--color-dim)" : down ? "var(--color-ok)" : "#E5626C";
  return (
    <svg width={width} height={(width / 72) * 22} viewBox="0 0 72 22" className="block" aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function FavButton({ fav, onClick, size = 17 }: { fav: boolean; onClick: () => void; size?: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={fav}
      title={fav ? "Retirer des favoris" : "Ajouter aux favoris"}
      className={`flex p-0.5 cursor-pointer transition-colors ${
        fav ? "text-gold" : "text-dim hover:text-gold"
      }`}
    >
      <Icon name="star" size={size} fill={fav ? "currentColor" : "none"} />
    </button>
  );
}

function Thumb({ src, alt, size }: { src: string | null; alt: string; size: "sm" | "lg" }) {
  const box = size === "sm" ? "w-[42px] h-[42px] rounded-[9px]" : "w-14 h-14 rounded-xl";
  return (
    <div
      className={`${box} bg-panel-2 border border-line flex items-center justify-center overflow-hidden shrink-0`}
    >
      {/* API-served reference art (same convention as the catalogue) — plain <img>
          because the host is the API origin, not the Next.js image pipeline. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {src && <img src={src} alt={alt} className="w-[86%] h-[86%] object-contain" />}
    </div>
  );
}

function ShopLink({ url, shop, block }: { url: string; shop: string; block?: boolean }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className={
        block
          ? "inline-flex items-center justify-center gap-[7px] text-accent text-[13px] font-semibold bg-accent-soft border border-accent-line px-3.5 py-2.5 rounded-[10px] whitespace-nowrap min-h-11"
          : "inline-flex items-center gap-1.5 text-accent text-[13px] whitespace-nowrap hover:text-ink transition-colors"
      }
    >
      {shop}
      <Icon name="externalLink" size={12} strokeWidth={2} />
    </a>
  );
}

function DashboardInner() {
  // Deep-link from the catalogue: /dashboard?game=&language=&set_code=&kind=&search=.
  // useSearchParams reads the query reliably on client navigation (unlike reading
  // window.location in an effect); we seed the initial filter state from it.
  const params = useSearchParams();
  const initGame = ((): "pokemon" | "optcg" => {
    const g = params.get("game");
    return g === "optcg" || g === "naruto_mythos" ? "optcg" : "pokemon";
  })();
  const deepLinked = !!(params.get("set_code") || params.get("kind"));

  const [game, setGame] = useState<"pokemon" | "optcg">(initGame);
  const [search, setSearch] = useState(params.get("search") ?? "");
  // Arriving via a set/type link: drop the default "In Stock" gate so the whole
  // filtered inventory is visible.
  const [status, setStatus] = useState<string[]>(deepLinked ? [] : ["In Stock"]);
  const [language, setLanguage] = useState<string>(params.get("language") ?? "");
  const [kind, setKind] = useState<string>(params.get("kind") ?? "");
  const [setCode, setSetCode] = useState<string>(params.get("set_code") ?? "");
  const [order, setOrder] = useState("default");
  const [page, setPage] = useState(0);

  const [data, setData] = useState<ProductListing[]>([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [setMap, setSetMap] = useState<Record<string, SetRef>>({});
  const [favByProduct, setFavByProduct] = useState<Record<number, number>>({});
  const [history, setHistory] = useState<Record<number, number[]>>({});
  const [loading, setLoading] = useState(false);

  const games = game === "pokemon" ? POKEMON : OPTCG;

  // Reference data (sets + facets + favorites) — reload when game changes.
  useEffect(() => {
    fetchFacets(games).then(setFacets).catch(() => {});
    fetchSets(game === "pokemon" ? "pokemon" : undefined).then((sets) => {
      const m: Record<string, SetRef> = {};
      sets.forEach((s) => { m[`${s.language}:${s.set_code}`] = s; });
      setSetMap(m);
    }).catch(() => {});
    listFavorites().then((favs: Favorite[]) => {
      const byp: Record<number, number> = {};
      favs.forEach((f) => { if (f.product_id) byp[f.product_id] = f.id; });
      setFavByProduct(byp);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game]);

  const load = useCallback(() => {
    setLoading(true);
    fetchProducts({
      game: games,
      status: status.length ? status : undefined,
      language: language ? [language] : undefined,
      kind: kind ? [kind] : undefined,
      set_code: setCode ? [setCode] : undefined,
      search: search || undefined,
      order,
      limit: PAGE,
      offset: page * PAGE,
    })
      .then((res) => { setData(res.items); setTotal(res.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [game, status, language, kind, setCode, search, order, page]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, [load]);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setPage(0); }, [game, status, language, kind, setCode, search, order]);

  // Trend sparklines: one batched call for the rows currently on screen.
  useEffect(() => {
    if (!data.length) return;
    let cancelled = false;
    fetchProductHistory(data.map((p) => p.product_id), HISTORY_DAYS)
      .then((res) => {
        if (cancelled) return;
        const m: Record<number, number[]> = {};
        Object.entries(res).forEach(([id, points]) => {
          m[Number(id)] = points.map((pt) => pt.p);
        });
        setHistory(m);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [data]);

  function setLabel(p: ProductListing) {
    if (!p.set_code) return "❓ set inconnu";
    const ref = setMap[`${p.language}:${p.set_code}`] ?? setMap[`en:${p.set_code}`];
    const block = p.series ? BLOCK_CODES[p.series] ?? "" : "";
    const abbr = ref?.abbreviation ?? "";
    const name = ref?.name ?? p.set_code;
    const pre = [block, abbr].filter(Boolean).join(" · ");
    return pre ? `${pre} · ${name}` : name;
  }

  async function toggleFav(p: ProductListing) {
    const existing = favByProduct[p.product_id];
    try {
      if (existing) {
        await deleteFavorite(existing);
        setFavByProduct((m) => { const n = { ...m }; delete n[p.product_id]; return n; });
      } else {
        const f = await addFavorite({ product_id: p.product_id });
        setFavByProduct((m) => ({ ...m, [p.product_id]: f.id }));
      }
    } catch { /* ignore */ }
  }

  const pages = Math.ceil(total / PAGE);
  const langs = useMemo(() => facets?.languages ?? [], [facets]);
  const kinds = useMemo(() => facets?.kinds ?? [], [facets]);
  const kindLabels = useMemo(() => facets?.kind_labels ?? {}, [facets]);
  const kindLabel = useCallback((k: string | null) => (k ? kindLabels[k] ?? k : "—"), [kindLabels]);
  const lastScan = useMemo(() => {
    const stamps = data.map((p) => p.observed_at).filter(Boolean) as string[];
    return stamps.length ? sinceLabel(stamps.sort().at(-1)!) : null;
  }, [data]);

  /** Everything a row needs, derived once for both the table and the cards. */
  const rows = useMemo(
    () =>
      data.map((p) => {
        const hist = history[p.product_id] ?? [];
        const delta = priceDelta(hist, p.price_now);
        return {
          p,
          hist,
          delta,
          fav: !!favByProduct[p.product_id],
          img: imageUrl(p.image),
          set: setLabel(p),
        };
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data, history, favByProduct, setMap],
  );

  const empty = !loading && rows.length === 0;

  return (
    <div>
      {/* ── Toolbar ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
        <div className="inline-flex bg-panel border border-line rounded-xl p-[3px] gap-[3px]">
          {(["pokemon", "optcg"] as const).map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => { setGame(g); setSetCode(""); }}
              aria-pressed={game === g}
              className={`px-4 py-2 rounded-[9px] text-[13px] font-semibold cursor-pointer transition-colors ${
                game === g ? "bg-accent-soft text-accent" : "text-muted hover:text-ink"
              }`}
            >
              {g === "pokemon" ? "Pokémon" : "One Piece / Naruto"}
            </button>
          ))}
        </div>

        {lastScan && (
          <div className="inline-flex items-center gap-2 text-xs text-dim">
            <span className="w-[7px] h-[7px] rounded-full bg-ok" />
            Dernier scan {lastScan}
          </div>
        )}
      </div>

      {/* ── Filtres ── */}
      <div className="flex flex-wrap gap-2 mb-3.5">
        <div className="relative flex-1 min-w-[min(100%,220px)]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-dim flex pointer-events-none">
            <Icon name="search" size={15} strokeWidth={2} />
          </span>
          <label htmlFor="dash-search" className="sr-only">Rechercher un produit</label>
          <input
            id="dash-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher (titre, set…)"
            className="w-full rounded-[10px] bg-panel border border-line-strong py-2.5 pl-9 pr-3 text-sm
                       text-ink placeholder-dim outline-none focus:border-accent transition-colors"
          />
        </div>

        <label htmlFor="dash-status" className="sr-only">Statut</label>
        <select id="dash-status" value={status[0] ?? ""} className={SELECT}
          onChange={(e) => setStatus(e.target.value ? [e.target.value] : [])}>
          <option value="">Tous statuts</option>
          <option value="In Stock">En stock</option>
          <option value="Out">Épuisé</option>
          <option value="Unknown">Inconnu</option>
        </select>

        {game === "pokemon" && (
          <>
            <label htmlFor="dash-lang" className="sr-only">Langue</label>
            <select id="dash-lang" value={language} className={SELECT}
              onChange={(e) => setLanguage(e.target.value)}>
              <option value="">Toutes langues</option>
              {langs.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
            </select>
          </>
        )}

        <label htmlFor="dash-kind" className="sr-only">Type d&apos;article</label>
        <select id="dash-kind" value={kind} className={SELECT} onChange={(e) => setKind(e.target.value)}>
          <option value="">Tous types</option>
          {kinds.map((k) => <option key={k} value={k}>{kindLabel(k)}</option>)}
        </select>

        <label htmlFor="dash-order" className="sr-only">Tri</label>
        <select id="dash-order" value={order} className={SELECT} onChange={(e) => setOrder(e.target.value)}>
          {ORDERS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {(setCode || kind) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {setCode && (
            <span className="inline-flex items-center gap-2 text-xs bg-accent-soft text-accent
                             border border-accent-line rounded-full px-3 py-1">
              Set : {setCode}
              <button type="button" onClick={() => setSetCode("")} title="Retirer le filtre set"
                className="cursor-pointer hover:text-ink">✕</button>
            </span>
          )}
          {kind && (
            <span className="inline-flex items-center gap-2 text-xs bg-accent-soft text-accent
                             border border-accent-line rounded-full px-3 py-1">
              Type : {kindLabel(kind)}
              <button type="button" onClick={() => setKind("")} title="Retirer le filtre type"
                className="cursor-pointer hover:text-ink">✕</button>
            </span>
          )}
        </div>
      )}

      <p className="text-xs text-dim mb-2.5">
        {loading
          ? "Chargement…"
          : `${total} produit${total > 1 ? "s" : ""} · triés par ${
              ORDERS.find((o) => o.value === order)?.label.toLowerCase() ?? order
            }`}
      </p>

      {/* ── Table (≥ 860px) ── */}
      <div className="hidden wide:block overflow-x-auto rounded-[14px] border border-line bg-panel">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-dim text-[11px] uppercase tracking-[0.08em]">
              <th className="font-semibold py-3 pl-4 pr-2 w-9" />
              <th className="font-semibold py-3 px-2">Produit</th>
              <th className="font-semibold py-3 px-2">Langue</th>
              <th className="font-semibold py-3 px-2">Type</th>
              <th className="font-semibold py-3 px-2">Statut</th>
              <th className="font-semibold py-3 px-2 text-right">Prix</th>
              <th className="font-semibold py-3 px-2">Tendance {HISTORY_DAYS} j</th>
              <th className="font-semibold py-3 pl-2 pr-4">Boutique</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, hist, delta, fav, img, set }) => (
              <tr key={p.product_id} className="border-t border-line hover:bg-panel-2 transition-colors">
                <td className="py-2.5 pl-4 pr-2">
                  <FavButton fav={fav} onClick={() => toggleFav(p)} />
                </td>
                <td className="py-2.5 px-2 min-w-[260px]">
                  <div className="flex items-center gap-3">
                    <Thumb src={img} alt="" size="sm" />
                    <div className="min-w-0">
                      <p className="font-semibold text-[13.5px] truncate max-w-[320px]" title={p.title}>
                        {p.title}
                      </p>
                      <p className="text-xs text-dim truncate mt-0.5">{set}</p>
                    </div>
                  </div>
                </td>
                <td className="py-2.5 px-2">
                  <span className="text-[11px] font-semibold font-mono bg-panel-2 border border-line-strong
                                   text-muted px-2 py-[3px] rounded-md">
                    {p.language.toUpperCase()}
                  </span>
                </td>
                <td className="py-2.5 px-2 text-muted text-[13px]">{kindLabel(p.kind)}</td>
                <td className="py-2.5 px-2"><StatusPill s={p.status} /></td>
                <td className="py-2.5 px-2 text-right whitespace-nowrap">
                  <span className="font-bold text-sm">{fmtPrice(p.price_now)}</span>
                  {delta && (
                    <span className={`text-[11.5px] font-semibold ml-1.5 ${delta.down ? "text-ok" : "text-[#E5626C]"}`}>
                      {delta.label}
                    </span>
                  )}
                </td>
                <td className="py-2.5 px-2">
                  <Sparkline hist={hist} down={delta ? delta.down : null} />
                </td>
                <td className="py-2.5 pl-2 pr-4">
                  <ShopLink url={p.url} shop={p.shop} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {empty && (
          <p className="p-8 text-center text-dim text-sm">Aucun produit ne correspond à ces filtres.</p>
        )}
      </div>

      {/* ── Cartes (< 860px) ── */}
      <div className="wide:hidden">
        <div className="grid gap-3 grid-cols-[repeat(auto-fill,minmax(min(100%,330px),1fr))]">
          {rows.map(({ p, hist, delta, fav, img, set }) => (
            <div key={p.product_id} className="bg-panel border border-line rounded-2xl p-3.5 flex flex-col gap-3">
              <div className="flex items-start gap-3">
                <Thumb src={img} alt="" size="lg" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-sm leading-[1.35]">{p.title}</p>
                  <p className="text-xs text-dim mt-[3px]">{set}</p>
                </div>
                <div className="flex justify-end min-w-11 min-h-11">
                  <FavButton fav={fav} onClick={() => toggleFav(p)} size={19} />
                </div>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] font-semibold font-mono bg-panel-2 border border-line-strong
                                 text-muted px-2 py-[3px] rounded-md">
                  {p.language.toUpperCase()}
                </span>
                {p.kind && (
                  <span className="text-[11.5px] text-muted bg-panel-2 border border-line px-2.5 py-[3px] rounded-full">
                    {kindLabel(p.kind)}
                  </span>
                )}
                <StatusPill s={p.status} small />
              </div>

              <div className="flex items-center justify-between gap-2.5 border-t border-line pt-3">
                <div className="flex items-center gap-2">
                  <span className="font-display font-bold text-[17px]">{fmtPrice(p.price_now)}</span>
                  {delta && (
                    <span className={`text-xs font-semibold ${delta.down ? "text-ok" : "text-[#E5626C]"}`}>
                      {delta.label}
                    </span>
                  )}
                  <Sparkline hist={hist} down={delta ? delta.down : null} width={60} />
                </div>
                <ShopLink url={p.url} shop={p.shop} block />
              </div>
            </div>
          ))}
        </div>
        {empty && (
          <p className="p-8 text-center text-dim text-sm">Aucun produit ne correspond à ces filtres.</p>
        )}
      </div>

      {/* ── Pagination ── */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-4 text-sm">
          <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1.5 rounded-[9px] bg-panel border border-line text-muted
                       hover:text-ink disabled:opacity-40 disabled:hover:text-muted cursor-pointer">
            ← Précédent
          </button>
          <span className="text-dim">Page {page + 1} / {pages}</span>
          <button type="button" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1.5 rounded-[9px] bg-panel border border-line text-muted
                       hover:text-ink disabled:opacity-40 disabled:hover:text-muted cursor-pointer">
            Suivant →
          </button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Protected>
      <Suspense fallback={<p className="text-dim">Chargement…</p>}>
        <DashboardInner />
      </Suspense>
    </Protected>
  );
}
