"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Protected from "@/components/Protected";
import {
  addFavorite,
  deleteFavorite,
  Facets,
  fetchFacets,
  fetchProducts,
  fetchSets,
  Favorite,
  listFavorites,
  ProductListing,
  SetRef,
} from "@/lib/api";

const POKEMON = ["pokemon"];
const OPTCG = ["optcg", "naruto_mythos"];
const BLOCK_CODES: Record<string, string> = {
  me: "ME", sv: "EV", swsh: "EB", sm: "SL", xy: "XY", bw: "NB", mc: "MCD",
};
const LANG_FLAG: Record<string, string> = {
  fr: "🇫🇷 FR", en: "🇬🇧 EN", ja: "🇯🇵 JA", ko: "🇰🇷 KO", zh: "🇨🇳 ZH",
};
const PAGE = 50;

function fmtPrice(p: number | null) {
  return p == null ? "—" : `${p.toFixed(2)} €`;
}

function StatusBadge({ s }: { s: string }) {
  const map: Record<string, string> = {
    "In Stock": "bg-green-500/15 text-green-400",
    Out: "bg-red-500/15 text-red-400",
    Unknown: "bg-gray-500/15 text-gray-400",
  };
  const label: Record<string, string> = { "In Stock": "En stock", Out: "Épuisé", Unknown: "?" };
  return <span className={`px-2 py-0.5 rounded-full text-xs ${map[s]}`}>{label[s] ?? s}</span>;
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

  return (
    <div>
      {/* Game toggle */}
      <div className="flex items-center gap-2 mb-5">
        {(["pokemon", "optcg"] as const).map((g) => (
          <button
            key={g}
            onClick={() => { setGame(g); setSetCode(""); }}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              game === g ? "bg-red-600 text-white" : "bg-gray-900 text-gray-400 hover:text-white"
            }`}
          >
            {g === "pokemon" ? "Pokémon" : "One Piece / Naruto"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <input
          value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher (titre, set…)"
          className="flex-1 min-w-50 rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm
                     focus:outline-none focus:border-red-500"
        />
        <select value={status[0] ?? ""} onChange={(e) => setStatus(e.target.value ? [e.target.value] : [])}
          className="rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm">
          <option value="">Tous statuts</option>
          <option value="In Stock">En stock</option>
          <option value="Out">Épuisé</option>
          <option value="Unknown">Inconnu</option>
        </select>
        {game === "pokemon" && (
          <select value={language} onChange={(e) => setLanguage(e.target.value)}
            className="rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm">
            <option value="">Toutes langues</option>
            {langs.map((l) => <option key={l} value={l}>{LANG_FLAG[l] ?? l}</option>)}
          </select>
        )}
        <select value={kind} onChange={(e) => setKind(e.target.value)}
          className="rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm">
          <option value="">Tous types</option>
          {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select value={order} onChange={(e) => setOrder(e.target.value)}
          className="rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm">
          <option value="default">Sets les plus récents</option>
          <option value="set_old">Sets les plus anciens</option>
          <option value="block">Par bloc / série</option>
          <option value="price_asc">Prix croissant</option>
          <option value="price_desc">Prix décroissant</option>
          <option value="recent">Derniers scans</option>
        </select>
      </div>

      {(setCode || kind) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {setCode && (
            <span className="inline-flex items-center gap-2 text-xs bg-red-500/15 text-red-300
                             border border-red-500/30 rounded-full px-3 py-1">
              Set : {setCode}
              <button onClick={() => setSetCode("")} title="Retirer le filtre set"
                className="hover:text-white">✕</button>
            </span>
          )}
          {kind && (
            <span className="inline-flex items-center gap-2 text-xs bg-red-500/15 text-red-300
                             border border-red-500/30 rounded-full px-3 py-1">
              Type : {kind}
              <button onClick={() => setKind("")} title="Retirer le filtre type"
                className="hover:text-white">✕</button>
            </span>
          )}
        </div>
      )}

      <p className="text-xs text-gray-500 mb-2">
        {loading ? "Chargement…" : `${total} produit(s)`}
      </p>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-white/5">
        <table className="w-full text-sm">
          <thead className="bg-gray-900 text-gray-400 text-left">
            <tr>
              <th className="px-3 py-2 w-8"></th>
              <th className="px-3 py-2">Produit</th>
              <th className="px-3 py-2">Set</th>
              <th className="px-3 py-2">Langue</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Statut</th>
              <th className="px-3 py-2 text-right">Prix</th>
              <th className="px-3 py-2">Boutique</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => {
              const fav = !!favByProduct[p.product_id];
              const drop = p.price_now != null && p.price_prev != null && p.price_now < p.price_prev;
              return (
                <tr key={p.product_id} className="border-t border-white/5 hover:bg-white/5">
                  <td className="px-3 py-2">
                    <button onClick={() => toggleFav(p)} title="Favori"
                      className={fav ? "text-amber-400" : "text-gray-600 hover:text-amber-400"}>
                      {fav ? "★" : "☆"}
                    </button>
                  </td>
                  <td className="px-3 py-2 max-w-xs truncate" title={p.title}>{p.title}</td>
                  <td className="px-3 py-2 text-gray-400">{setLabel(p)}</td>
                  <td className="px-3 py-2">{LANG_FLAG[p.language] ?? p.language}</td>
                  <td className="px-3 py-2 text-gray-400">{p.kind ?? "—"}</td>
                  <td className="px-3 py-2"><StatusBadge s={p.status} /></td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {fmtPrice(p.price_now)}
                    {drop && <span className="ml-1 text-green-400 text-xs">↓</span>}
                  </td>
                  <td className="px-3 py-2">
                    <a href={p.url} target="_blank" rel="noreferrer"
                      className="text-red-400 hover:text-red-300">{p.shop}</a>
                  </td>
                </tr>
              );
            })}
            {!loading && data.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-8 text-center text-gray-500">Aucun produit.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-4 text-sm">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1 rounded bg-gray-900 disabled:opacity-40">← Précédent</button>
          <span className="text-gray-500">Page {page + 1} / {pages}</span>
          <button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1 rounded bg-gray-900 disabled:opacity-40">Suivant →</button>
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Protected>
      <Suspense fallback={<p className="text-gray-500">Chargement…</p>}>
        <DashboardInner />
      </Suspense>
    </Protected>
  );
}
