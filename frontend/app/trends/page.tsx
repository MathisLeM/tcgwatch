"use client";

import { useEffect, useMemo, useState } from "react";
import Protected from "@/components/Protected";
import { TrendItem, TrendPoint, fetchTrends, imageUrl } from "@/lib/api";

function fmt(p?: number | null) {
  return p == null ? "—" : `${p.toFixed(2)} €`;
}

function DeltaBadge({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-dim text-xs">—</span>;
  const up = pct >= 0;
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded-full ${
      up ? "bg-ok-soft text-ok" : "bg-accent-soft text-accent"
    }`}>
      {up ? "▲" : "▼"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

/** Minimal inline SVG sparkline from trend points. */
function Sparkline({ points, up, w = 130, h = 34 }: {
  points: TrendPoint[]; up: boolean; w?: number; h?: number;
}) {
  const vals = points.map((p) => p.t).filter((t): t is number => t != null);
  if (vals.length < 2) return <div className="text-dim text-xs">série courte</div>;
  const pad = 3;
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const step = (w - 2 * pad) / (vals.length - 1);
  const coords = vals.map((v, i) => [pad + i * step, pad + (h - 2 * pad) * (1 - (v - min) / range)]);
  const line = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const color = up ? "#4ade80" : "#f87171";
  const [lx, ly] = coords[coords.length - 1];
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={line} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lx} cy={ly} r={2} fill={color} />
    </svg>
  );
}

function itemCode(it: TrendItem) {
  return it.category === "sealed" ? `${it.set_code} · ${it.kind}` : it.card_code;
}

function TrendCard({ it, onOpen }: { it: TrendItem; onOpen: (it: TrendItem) => void }) {
  const img = imageUrl(it.image);
  const up = (it.delta_pct ?? 0) >= 0;
  return (
    <button
      onClick={() => onOpen(it)}
      className="text-left rounded-xl border border-line bg-panel p-4 hover:border-accent transition-colors"
    >
      <div className="flex gap-3">
        {it.category === "sealed" && (
          <div className="w-14 h-14 shrink-0 flex items-center justify-center rounded-lg bg-panel-2 overflow-hidden">
            {img ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={img} alt={it.name} className="max-h-14 max-w-14 object-contain" />
            ) : <span className="text-lg text-dim">📦</span>}
          </div>
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-mono text-muted">{itemCode(it)}</p>
          <p className="text-sm font-medium leading-snug truncate" title={it.name}>{it.name}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-base font-semibold">{fmt(it.latest?.trend)}</span>
            <DeltaBadge pct={it.delta_pct} />
          </div>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Sparkline points={it.points} up={up} />
        <span className="text-[11px] text-dim">bas {fmt(it.latest?.low)}</span>
      </div>
    </button>
  );
}

function DetailModal({ it, onClose }: { it: TrendItem; onClose: () => void }) {
  const up = (it.delta_pct ?? 0) >= 0;
  const vals = it.points.map((p) => p.t).filter((t): t is number => t != null);
  const min = vals.length ? Math.min(...vals) : null;
  const max = vals.length ? Math.max(...vals) : null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl border border-line-strong bg-canvas p-5"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-mono text-muted">{itemCode(it)}</p>
            <h2 className="font-semibold">{it.name}</h2>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink">✕</button>
        </div>
        <div className="my-4 rounded-lg bg-panel p-3">
          <Sparkline points={it.points} up={up} w={480} h={120} />
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <Stat label="Tendance" value={fmt(it.latest?.trend)} />
          <Stat label="Δ depuis le début" value={it.delta_pct == null ? "—" : `${it.delta_pct.toFixed(1)} %`}
            color={up ? "text-ok" : "text-accent"} />
          <Stat label="Bas actuel" value={fmt(it.latest?.low)} />
          <Stat label="Min" value={fmt(min)} />
          <Stat label="Max" value={fmt(max)} />
          <Stat label="1er relevé" value={`${fmt(it.first_trend)}`} sub={it.first_on ?? ""} />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="rounded-lg bg-panel px-3 py-2">
      <p className="text-[11px] text-dim">{label}</p>
      <p className={`font-semibold ${color ?? ""}`}>{value}</p>
      {sub && <p className="text-[10px] text-dim">{sub}</p>}
    </div>
  );
}

function TrendsInner() {
  const [category, setCategory] = useState<"sealed" | "single">("sealed");
  const [items, setItems] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<TrendItem | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    fetchTrends(category)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [category]);

  const gainers = useMemo(
    () => [...items].filter((i) => i.delta_pct != null).sort((a, b) => (b.delta_pct ?? 0) - (a.delta_pct ?? 0)),
    [items],
  );

  return (
    <div>
      <div className="flex items-end justify-between gap-3 flex-wrap mb-1">
        <h1 className="text-xl font-semibold">Tendances — One Piece 🏴‍☠️</h1>
        <div className="flex gap-2">
          {(["sealed", "single"] as const).map((c) => (
            <button key={c} onClick={() => setCategory(c)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                category === c ? "bg-accent text-on-accent" : "bg-panel text-muted hover:text-ink"
              }`}>
              {c === "sealed" ? "Scellés" : "Cartes (singles)"}
            </button>
          ))}
        </div>
      </div>
      <p className="text-sm text-muted mb-5">
        Valeur de marché <strong>Cardmarket</strong> (€) et son évolution. Clique un article pour l&apos;historique.
      </p>

      {loading && <p className="text-dim">Chargement…</p>}
      {!loading && items.length === 0 && (
        <p className="text-dim">Aucun article suivi. Ajoute-en via <code>scraper.cardmarket.track</code>.</p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {gainers.map((it) => <TrendCard key={it.id_product} it={it} onOpen={setSelected} />)}
      </div>

      {selected && <DetailModal it={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

export default function TrendsPage() {
  return (
    <Protected>
      <TrendsInner />
    </Protected>
  );
}
