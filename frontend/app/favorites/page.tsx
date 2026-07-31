"use client";

import { useEffect, useState } from "react";
import Protected from "@/components/Protected";
import {
  deleteFavorite,
  Favorite,
  listFavorites,
  listFavoriteListings,
  ProductListing,
} from "@/lib/api";

const LANG_FLAG: Record<string, string> = {
  fr: "🇫🇷 FR", en: "🇬🇧 EN", ja: "🇯🇵 JA", ko: "🇰🇷 KO", zh: "🇨🇳 ZH",
};

function FavoritesInner() {
  const [items, setItems] = useState<ProductListing[]>([]);
  const [favByProduct, setFavByProduct] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);

  function reload() {
    setLoading(true);
    Promise.all([listFavoriteListings(), listFavorites()])
      .then(([listings, favs]: [ProductListing[], Favorite[]]) => {
        setItems(listings);
        const m: Record<number, number> = {};
        favs.forEach((f) => { if (f.product_id) m[f.product_id] = f.id; });
        setFavByProduct(m);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(reload, []);

  async function remove(productId: number) {
    const id = favByProduct[productId];
    if (!id) return;
    await deleteFavorite(id);
    setItems((xs) => xs.filter((p) => p.product_id !== productId));
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-1">Mes favoris</h1>
      <p className="text-sm text-muted mb-5">
        {loading ? "Chargement…" : `${items.length} produit(s) suivi(s)`}
      </p>

      {!loading && items.length === 0 && (
        <p className="text-dim">
          Aucun favori. Ajoutez-en avec l&apos;étoile ☆ depuis le dashboard.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((p) => (
          <div key={p.product_id} className="bg-panel border border-line rounded-xl p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium leading-snug">{p.title}</p>
              <button onClick={() => remove(p.product_id)} title="Retirer"
                className="text-gold hover:text-gold shrink-0">★</button>
            </div>
            <p className="text-xs text-dim mt-1">
              {p.set_code || "?"} · {LANG_FLAG[p.language] ?? p.language} · {p.kind ?? "—"}
            </p>
            <div className="flex items-center justify-between mt-3">
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                p.status === "In Stock" ? "bg-ok-soft text-ok"
                : p.status === "Out" ? "bg-accent-soft text-accent"
                : "bg-panel-2 text-muted"}`}>
                {p.status === "In Stock" ? "En stock" : p.status === "Out" ? "Épuisé" : "?"}
              </span>
              <span className="text-sm font-semibold">
                {p.price_now == null ? "—" : `${p.price_now.toFixed(2)} €`}
              </span>
            </div>
            <a href={p.url} target="_blank" rel="noreferrer"
              className="block mt-2 text-xs text-accent hover:text-ink">{p.shop} ↗</a>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function FavoritesPage() {
  return (
    <Protected>
      <FavoritesInner />
    </Protected>
  );
}
