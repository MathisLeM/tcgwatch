"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Protected from "@/components/Protected";
import {
  Catalog,
  CatalogBlock,
  CatalogGame,
  CatalogSet,
  fetchCatalog,
  fetchGames,
  imageUrl,
} from "@/lib/api";

const LANG_FLAG: Record<string, string> = {
  fr: "🇫🇷 FR", en: "🇬🇧 EN", ja: "🇯🇵 JA", ko: "🇰🇷 KO", zh: "🇨🇳 ZH",
};
const GAME_EMOJI: Record<string, string> = {
  pokemon: "⚡", optcg: "🏴‍☠️", naruto_mythos: "🍥",
};

/** Deep-link into the product table, pre-filtered. */
function dashHref(game: string, opts: { set_code?: string; language?: string; kind?: string } = {}) {
  const p = new URLSearchParams({ game });
  if (opts.language) p.set("language", opts.language);
  if (opts.set_code) p.set("set_code", opts.set_code);
  if (opts.kind) p.set("kind", opts.kind);
  return `/dashboard?${p.toString()}`;
}

function year(d?: string | null) {
  return d ? d.slice(0, 4) : "";
}

function fmtPrice(p?: number | null) {
  return p == null ? null : `${p.toFixed(2)} €`;
}

/** Availability preview: "2/20 dispo · dès 24.90 €". */
function Stock({ avail, total, minPrice }: { avail: number; total: number; minPrice?: number | null }) {
  const price = fmtPrice(minPrice);
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={`px-1.5 py-0.5 rounded-full font-medium ${
        avail > 0 ? "bg-green-500/15 text-green-400" : "bg-gray-500/10 text-gray-500"
      }`}>
        {avail}/{total} dispo
      </span>
      {price && <span className="text-gray-300">dès {price}</span>}
    </span>
  );
}

// ── Level 0: TCG chooser ─────────────────────────────────────────────────────
function GameChooser({ games, onSelect }: { games: CatalogGame[]; onSelect: (g: CatalogGame) => void }) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Catalogue</h1>
      <p className="text-sm text-gray-400 mb-6">Choisis un jeu pour parcourir ses sets et types d&apos;articles.</p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {games.map((g) => {
          const img = imageUrl(g.image);
          return (
            <button
              key={g.game}
              onClick={() => onSelect(g)}
              className="text-left rounded-2xl border border-white/10 bg-gray-900 p-5
                         hover:border-red-500 transition-colors"
            >
              <div className="h-24 flex items-center justify-center mb-3">
                {img ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={img} alt={g.label} className="max-h-24 max-w-full object-contain" />
                ) : (
                  <span className="text-5xl">{GAME_EMOJI[g.game] ?? "🎴"}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-lg">{GAME_EMOJI[g.game] ?? "🎴"}</span>
                <span className="text-lg font-semibold">{g.label}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {g.set_count} sets · {g.product_count} fiches
              </p>
              <div className="mt-2">
                <Stock avail={g.available_count} total={g.product_count} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Set card (shared by both modes) ──────────────────────────────────────────
function SetCard({ game, set }: { game: string; set: CatalogSet }) {
  const img = imageUrl(set.image);
  return (
    <div className="rounded-xl border border-white/5 bg-gray-900 p-4 flex flex-col">
      <div className="flex gap-3">
        <div className="w-16 h-16 shrink-0 flex items-center justify-center rounded-lg bg-white/5 overflow-hidden">
          {img ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={img} alt={set.name} className="max-h-16 max-w-16 object-contain" />
          ) : (
            <span className="text-xl text-gray-600">🃏</span>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            {set.abbreviation && (
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-gray-300">
                {set.abbreviation}
              </span>
            )}
            <span className="text-[11px] text-gray-500">{LANG_FLAG[set.language] ?? set.language}</span>
          </div>
          <Link
            href={dashHref(game, { set_code: set.set_code, language: set.language })}
            className="block mt-0.5 font-medium leading-snug hover:text-red-400"
          >
            {set.name}
          </Link>
          <p className="text-xs text-gray-500 mt-0.5">
            {year(set.release_date)}
            {set.card_count ? ` · ${set.card_count} cartes` : ""}
            {` · ${set.product_count} fiche${set.product_count > 1 ? "s" : ""}`}
          </p>
          <div className="mt-1">
            <Stock avail={set.available_count} total={set.product_count} minPrice={set.min_price} />
          </div>
        </div>
      </div>
      {set.kinds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {set.kinds.map((k) => {
            const av = k.available_count ?? 0;
            const price = fmtPrice(k.min_price);
            return (
              <Link
                key={k.kind}
                href={dashHref(game, { set_code: set.set_code, language: set.language, kind: k.kind })}
                title={`${k.label} — ${av}/${k.product_count} en stock${price ? ` · dès ${price}` : ""}`}
                className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10
                           text-gray-300 hover:border-red-500 hover:text-white transition-colors"
              >
                {k.label}{" "}
                <span className={av > 0 ? "text-green-400" : "text-gray-500"}>{av}/{k.product_count}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SetsGrid({ game, sets }: { game: string; sets: CatalogSet[] }) {
  if (sets.length === 0) return <p className="text-gray-500">Aucun set avec des annonces.</p>;
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {sets.map((s) => <SetCard key={`${s.language}:${s.set_code}`} game={game} set={s} />)}
    </div>
  );
}

// ── Pokemon blocks view ──────────────────────────────────────────────────────
function BlocksView({ data }: { data: Catalog }) {
  const blocks = useMemo(() => data.blocks ?? [], [data.blocks]);
  const [selected, setSelected] = useState<string | null>(null);
  const [showEmpty, setShowEmpty] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelected((cur) =>
      cur && blocks.some((b) => b.block === cur)
        ? cur
        : (blocks.find((b) => b.product_count > 0) ?? blocks[0])?.block ?? null,
    );
  }, [blocks]);

  const block: CatalogBlock | null = useMemo(
    () => blocks.find((b) => b.block === selected) ?? null,
    [blocks, selected],
  );
  const sets = useMemo(() => {
    if (!block) return [];
    return showEmpty ? block.sets : block.sets.filter((s) => s.product_count > 0);
  }, [block, showEmpty]);

  return (
    <div>
      <div className="flex gap-3 overflow-x-auto pb-2 mb-6">
        {blocks.map((b) => {
          const img = imageUrl(b.image);
          const active = b.block === selected;
          return (
            <button
              key={b.block}
              onClick={() => setSelected(b.block)}
              className={`shrink-0 w-44 text-left rounded-xl border p-3 transition-colors ${
                active ? "border-red-500 bg-red-500/10" : "border-white/5 bg-gray-900 hover:border-white/20"
              }`}
            >
              <div className="h-16 flex items-center justify-center mb-2">
                {img ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={img} alt={b.name.fr} className="max-h-16 max-w-full object-contain" />
                ) : (
                  <span className="text-2xl">🎴</span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-gray-300">
                  {b.block_code}
                </span>
                <span className="text-sm font-medium leading-tight truncate">{b.name.fr}</span>
              </div>
              <p className="text-xs text-gray-500 mt-1">{b.set_count} sets · {b.product_count} fiches</p>
              <div className="mt-1">
                <Stock avail={b.available_count} total={b.product_count} minPrice={b.min_price} />
              </div>
            </button>
          );
        })}
      </div>

      {block && (
        <div>
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="text-lg font-medium">
              {block.name.fr}
              <span className="ml-2 text-sm text-gray-500">
                {block.product_count} annonce{block.product_count > 1 ? "s" : ""}
              </span>
            </h2>
            <label className="text-xs text-gray-400 flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={showEmpty} onChange={(e) => setShowEmpty(e.target.checked)}
                className="accent-red-600" />
              Sets sans annonce
            </label>
          </div>
          <SetsGrid game="pokemon" sets={sets} />
        </div>
      )}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────────────────────
function CatalogInner() {
  const [games, setGames] = useState<CatalogGame[]>([]);
  const [game, setGame] = useState<CatalogGame | null>(null);
  const [data, setData] = useState<Catalog | null>(null);
  const [language, setLanguage] = useState("fr");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchGames().then(setGames).catch(() => setGames([]));
  }, []);

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!game) { setData(null); return; }
    setLoading(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    fetchCatalog(game.game, game.mode === "blocks" ? language : undefined)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [game, language]);

  if (!game) {
    return games.length === 0
      ? <p className="text-gray-500">Chargement…</p>
      : <GameChooser games={games} onSelect={setGame} />;
  }

  return (
    <div>
      {/* Breadcrumb + game-level "voir tous" */}
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <button onClick={() => { setGame(null); setData(null); }}
            className="text-gray-400 hover:text-white">Catalogue</button>
          <span className="text-gray-600">/</span>
          <span className="font-semibold">{GAME_EMOJI[game.game]} {game.label}</span>
        </div>
        <div className="flex items-center gap-2">
          {game.mode === "blocks" && (
            <select value={language} onChange={(e) => setLanguage(e.target.value)}
              className="rounded-lg bg-gray-900 border border-white/10 px-3 py-1.5 text-sm">
              {Object.keys(LANG_FLAG).map((l) => <option key={l} value={l}>{LANG_FLAG[l]}</option>)}
            </select>
          )}
          <Link href={dashHref(game.game)}
            className="text-sm px-3 py-1.5 rounded-lg bg-gray-900 border border-white/10
                       text-gray-300 hover:border-red-500 hover:text-white transition-colors">
            Voir tous les items →
          </Link>
        </div>
      </div>

      {loading && <p className="text-gray-500">Chargement…</p>}
      {!loading && data && data.mode === "blocks" && <BlocksView data={data} />}
      {!loading && data && data.mode === "sets" && <SetsGrid game={game.game} sets={data.sets ?? []} />}

      {!loading && data && data.unassigned.product_count > 0 && (
        <div className="mt-8 rounded-xl border border-white/5 bg-gray-900 p-4">
          <h3 className="text-sm font-medium">
            Sans set identifié
            <span className="ml-2 text-xs text-gray-500">
              {data.unassigned.product_count} annonce(s)
            </span>
          </h3>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {data.unassigned.kinds.map((k) => (
              <span key={k.kind}
                className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400">
                {k.label} <span className="text-gray-600">·{k.product_count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function CatalogPage() {
  return (
    <Protected>
      <CatalogInner />
    </Protected>
  );
}
