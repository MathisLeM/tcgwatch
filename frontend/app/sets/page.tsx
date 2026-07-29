"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import Protected from "@/components/Protected";
import {
  BlockHierarchy,
  HierarchyBlock,
  HierarchySet,
  fetchBlocks,
  imageUrl,
} from "@/lib/api";

const LANG_FLAG: Record<string, string> = {
  fr: "🇫🇷 FR", en: "🇬🇧 EN", ja: "🇯🇵 JA", ko: "🇰🇷 KO", zh: "🇨🇳 ZH",
};
const LANGS = ["fr", "en", "ja", "ko", "zh"];

/** Deep-link into the dashboard, pre-filtered on a set (and optionally a type). */
function dashHref(set: HierarchySet, kind?: string) {
  const p = new URLSearchParams({
    game: "pokemon",
    language: set.language,
    set_code: set.set_code,
  });
  if (kind) p.set("kind", kind);
  return `/dashboard?${p.toString()}`;
}

function year(d: string | null) {
  return d ? d.slice(0, 4) : "";
}

function BlockCard({
  block, active, onSelect,
}: { block: HierarchyBlock; active: boolean; onSelect: () => void }) {
  const img = imageUrl(block.image);
  return (
    <button
      onClick={onSelect}
      className={`shrink-0 w-44 text-left rounded-xl border p-3 transition-colors ${
        active
          ? "border-red-500 bg-red-500/10"
          : "border-white/5 bg-gray-900 hover:border-white/20"
      }`}
    >
      <div className="h-16 flex items-center justify-center mb-2">
        {img ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={img} alt={block.name.fr} className="max-h-16 max-w-full object-contain" />
        ) : (
          <span className="text-2xl">🎴</span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/10 text-gray-300">
          {block.block_code}
        </span>
        <span className="text-sm font-medium leading-tight truncate">{block.name.fr}</span>
      </div>
      <p className="text-xs text-gray-500 mt-1">
        {block.set_count} sets · {block.product_count} annonces
      </p>
    </button>
  );
}

function SetCard({ set }: { set: HierarchySet }) {
  const img = imageUrl(set.image);
  return (
    <div className="rounded-xl border border-white/5 bg-gray-900 p-4 flex flex-col">
      <div className="flex gap-3">
        <div className="w-16 h-16 shrink-0 flex items-center justify-center rounded-lg bg-white/5">
          {img ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={img} alt={set.name} className="max-h-14 max-w-14 object-contain" />
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
          <Link href={dashHref(set)} className="block mt-0.5 font-medium leading-snug hover:text-red-400">
            {set.name}
          </Link>
          <p className="text-xs text-gray-500 mt-0.5">
            {year(set.release_date)}
            {set.card_count ? ` · ${set.card_count} cartes` : ""}
            {" · "}
            {set.product_count} annonce{set.product_count > 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Article types */}
      {set.kinds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {set.kinds.map((k) => (
            <Link
              key={k.kind}
              href={dashHref(set, k.kind)}
              title={`${k.label} — ${k.product_count} annonce(s)`}
              className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10
                         text-gray-300 hover:border-red-500 hover:text-white transition-colors"
            >
              {k.label} <span className="text-gray-500">·{k.product_count}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function SetsInner() {
  const [language, setLanguage] = useState<string>("");
  const [data, setData] = useState<BlockHierarchy | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [showEmpty, setShowEmpty] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetchBlocks(language || undefined)
      .then((h) => {
        setData(h);
        // Default-select the first block that actually has tracked listings.
        setSelected((cur) => {
          if (cur && h.blocks.some((b) => b.block === cur)) return cur;
          return (h.blocks.find((b) => b.product_count > 0) ?? h.blocks[0])?.block ?? null;
        });
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [language]);

  const block = useMemo(
    () => data?.blocks.find((b) => b.block === selected) ?? null,
    [data, selected],
  );

  const sets = useMemo(() => {
    if (!block) return [];
    return showEmpty ? block.sets : block.sets.filter((s) => s.product_count > 0);
  }, [block, showEmpty]);

  return (
    <div>
      <div className="flex items-end justify-between gap-3 flex-wrap mb-1">
        <h1 className="text-xl font-semibold">Catalogue Pokémon</h1>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="rounded-lg bg-gray-900 border border-white/10 px-3 py-2 text-sm"
        >
          <option value="">Toutes langues</option>
          {LANGS.map((l) => <option key={l} value={l}>{LANG_FLAG[l]}</option>)}
        </select>
      </div>
      <p className="text-sm text-gray-400 mb-5">
        Parcourez par <strong>bloc</strong>, puis <strong>set</strong>, puis <strong>type d&apos;article</strong>.
        {" "}Cliquez un type pour voir les annonces correspondantes.
      </p>

      {loading && <p className="text-gray-500">Chargement…</p>}

      {!loading && data && (
        <>
          {/* Level 1 — blocks */}
          <div className="flex gap-3 overflow-x-auto pb-2 mb-6">
            {data.blocks.map((b) => (
              <BlockCard
                key={b.block}
                block={b}
                active={b.block === selected}
                onSelect={() => setSelected(b.block)}
              />
            ))}
          </div>

          {/* Level 2 + 3 — sets & article types for the selected block */}
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
                  <input
                    type="checkbox"
                    checked={showEmpty}
                    onChange={(e) => setShowEmpty(e.target.checked)}
                    className="accent-red-600"
                  />
                  Afficher les sets sans annonce
                </label>
              </div>

              {sets.length === 0 ? (
                <p className="text-gray-500">Aucun set avec des annonces dans ce bloc.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {sets.map((s) => (
                    <SetCard key={`${s.language}:${s.set_code}`} set={s} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Setless listings (old sets / standalone tins) */}
          {data.unassigned.product_count > 0 && (
            <div className="mt-8 rounded-xl border border-white/5 bg-gray-900 p-4">
              <h3 className="text-sm font-medium">
                Sans set identifié
                <span className="ml-2 text-xs text-gray-500">
                  {data.unassigned.product_count} annonce(s) — sets hors référence (pré-2020) ou tins autonomes
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
        </>
      )}
    </div>
  );
}

export default function SetsPage() {
  return (
    <Protected>
      <SetsInner />
    </Protected>
  );
}
