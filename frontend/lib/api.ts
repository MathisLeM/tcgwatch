// Typed fetch wrappers around the TCGWatch API.
// All backend calls go through here (Vigilyx convention). Auth uses an httpOnly
// cookie, so every request sends credentials.
// Strip any trailing slash(es) so `${API}${path}` never produces a double slash
// (`https://api//auth/login` 404s). Guards against NEXT_PUBLIC_API_URL being set
// with a trailing "/".
const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const res = await fetch(`${API}${path}`, { ...options, headers, credentials: "include" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Erreur API");
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────
export interface UserInfo {
  id: number;
  email: string;
  is_admin: boolean;
}

export async function login(email: string, password: string): Promise<UserInfo> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    credentials: "include",
    body: body.toString(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Connexion échouée" }));
    throw new Error(err.detail ?? "Connexion échouée");
  }
  return res.json();
}

export async function signup(email: string, password: string): Promise<UserInfo> {
  return request<UserInfo>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export const fetchMe = () => request<UserInfo>("/auth/me");
export const apiLogout = () => request<void>("/auth/logout", { method: "POST" });

// ── Products ────────────────────────────────────────────────────────────────
export interface ProductListing {
  product_id: number;
  platform: string;
  shop: string;
  game: string;
  language: string;
  set_code: string;
  set_codes: string | null;
  series: string | null;
  kind: string | null;
  title: string;
  url: string;
  price_now: number | null;
  available: number | null;
  status: "In Stock" | "Out" | "Unknown";
  stock_remaining: number | null;
  observed_at: string | null;
  price_prev: number | null;
  avail_prev: number | null;
  image: string | null;   // root-relative, e.g. "images/Pokemon/..." — see imageUrl()
}

/** One day of a product's price history (last observation of that day). */
export interface PricePoint {
  d: string;   // ISO date, YYYY-MM-DD
  p: number;   // EUR
}

/**
 * Price series for several products in one call — the dashboard asks for every
 * row on the current page at once. Products with no data in the window come back
 * as an empty array, never absent.
 */
export const fetchProductHistory = (productIds: number[], days = 30) => {
  const p = new URLSearchParams();
  productIds.forEach((id) => p.append("product_id", String(id)));
  p.set("days", String(days));
  return request<Record<string, PricePoint[]>>(`/products/history?${p.toString()}`);
};

export interface ProductPage {
  total: number;
  limit: number;
  offset: number;
  items: ProductListing[];
}

export interface ProductQuery {
  game?: string[];
  language?: string[];
  set_code?: string[];
  series?: string[];
  kind?: string[];
  shop?: string[];
  status?: string[];
  max_price?: number;
  search?: string;
  order?: string;
  limit?: number;
  offset?: number;
}

function toQuery(q: ProductQuery): string {
  const p = new URLSearchParams();
  const addAll = (k: string, v?: string[]) => v?.forEach((x) => p.append(k, x));
  addAll("game", q.game);
  addAll("language", q.language);
  addAll("set_code", q.set_code);
  addAll("series", q.series);
  addAll("kind", q.kind);
  addAll("shop", q.shop);
  addAll("status", q.status);
  if (q.max_price != null) p.set("max_price", String(q.max_price));
  if (q.search) p.set("search", q.search);
  if (q.order) p.set("order", q.order);
  if (q.limit != null) p.set("limit", String(q.limit));
  if (q.offset != null) p.set("offset", String(q.offset));
  return p.toString();
}

export const fetchProducts = (q: ProductQuery = {}) =>
  request<ProductPage>(`/products?${toQuery(q)}`);

export interface Facets {
  games: string[];
  languages: string[];
  series: string[];
  kinds: string[];
  /** Readable label per kind slug ("etb" -> "Coffret Dresseur d'Élite (ETB)"). */
  kind_labels: Record<string, string>;
  shops: string[];
  set_codes: string[];
}

export const fetchFacets = (games?: string[]) => {
  const p = new URLSearchParams();
  games?.forEach((g) => p.append("game", g));
  return request<Facets>(`/products/facets?${p.toString()}`);
};

// ── Sets ────────────────────────────────────────────────────────────────────
export interface SetRef {
  game: string;
  language: string;
  set_code: string;
  name: string | null;
  abbreviation: string | null;
  series: string | null;
  logo_url: string | null;
  symbol_url: string | null;
  card_count: number | null;
}

export const fetchSets = (game?: string, language?: string) => {
  const p = new URLSearchParams();
  if (game) p.set("game", game);
  if (language) p.set("language", language);
  return request<SetRef[]>(`/sets?${p.toString()}`);
};

// ── Blocks navigation (block > set > article type) ───────────────────────────
export interface BlockKind {
  kind: string;
  label: string;
  label_en?: string;
  product_count: number;
}

export interface HierarchySet {
  language: string;
  set_code: string;
  abbreviation: string;
  number: string;
  name: string;
  release_date: string | null;
  card_count: number | null;
  image: string | null;   // root-relative, e.g. "images/Pokemon/..."
  logo_url: string | null;
  block: string;
  product_count: number;
  kinds: BlockKind[];
}

export interface HierarchyBlock {
  block: string;
  block_code: string;
  name: { fr: string; en: string };
  image: string | null;
  release_start: string | null;
  release_end: string | null;
  set_count: number;
  product_count: number;
  sets: HierarchySet[];
}

export interface BlockHierarchy {
  built_at: string;
  languages: string[];
  block_count: number;
  blocks: HierarchyBlock[];
  unassigned: { product_count: number; kinds: BlockKind[] };
}

export const fetchBlocks = (language?: string) => {
  const p = new URLSearchParams();
  if (language) p.set("language", language);
  return request<BlockHierarchy>(`/sets/blocks?${p.toString()}`);
};

/** Absolute URL for a root-relative reference image path (block/set logo). */
export const imageUrl = (path: string | null | undefined) =>
  path ? `${API}/${path.split("/").map(encodeURIComponent).join("/")}` : null;

// ── Multi-TCG catalogue (TCG > (block >) set > article type) ──────────────────
export interface CatalogGame {
  game: string;
  label: string;
  mode: "blocks" | "sets";
  product_count: number;
  available_count: number;
  set_count: number;
  image: string | null;
}

export const fetchGames = () => request<CatalogGame[]>("/catalog/games");

export interface CatalogKind {
  kind: string;
  label: string;
  label_en?: string;
  product_count: number;
  available_count?: number;
  min_price?: number | null;
  image?: string | null;
}

export interface CatalogSet {
  set_code: string;
  language: string;
  abbreviation: string;
  name: string;
  image: string | null;
  product_count: number;
  available_count: number;
  min_price: number | null;
  kinds: CatalogKind[];
  release_date?: string | null;
  number?: string;
  card_count?: number | null;
  block?: string;
}

export interface CatalogBlock {
  block: string;
  block_code: string;
  name: { fr: string; en: string };
  image: string | null;
  release_start: string | null;
  release_end: string | null;
  set_count: number;
  product_count: number;
  available_count: number;
  min_price: number | null;
  sets: CatalogSet[];
}

export interface Catalog {
  game: string;
  mode: "blocks" | "sets";
  language?: string;
  blocks?: CatalogBlock[];
  sets?: CatalogSet[];
  block_count?: number;
  set_count?: number;
  unassigned: { product_count: number; kinds: CatalogKind[] };
}

export const fetchCatalog = (game: string, language?: string) => {
  const p = new URLSearchParams({ game });
  if (language) p.set("language", language);
  return request<Catalog>(`/catalog?${p.toString()}`);
};

// ── Cardmarket price trends (sealed + singles) ───────────────────────────────
export interface TrendPoint {
  d: string;        // ISO date
  t: number | null; // trend price
}

export interface TrendItem {
  id_product: number;
  category: "sealed" | "single";
  name: string;
  set_code: string | null;
  kind: string | null;
  card_code: string | null;
  card_set: string | null;
  image: string | null;
  latest: { observed_on: string; trend: number | null; low: number | null; avg: number | null } | null;
  first_on: string | null;
  first_trend: number | null;
  delta_pct: number | null;
  points: TrendPoint[];
}

export const fetchTrends = (category?: "sealed" | "single", game = "optcg") => {
  const p = new URLSearchParams({ game });
  if (category) p.set("category", category);
  return request<TrendItem[]>(`/trends?${p.toString()}`);
};

// ── Favorites ───────────────────────────────────────────────────────────────
export interface Favorite {
  id: number;
  product_id: number | null;
  catalog_id: number | null;
  created_at: string;
}

export const listFavorites = () => request<Favorite[]>("/favorites");
export const listFavoriteListings = () => request<ProductListing[]>("/favorites/listings");
export const addFavorite = (target: { product_id?: number; catalog_id?: number }) =>
  request<Favorite>("/favorites", { method: "POST", body: JSON.stringify(target) });
export const deleteFavorite = (id: number) =>
  request<void>(`/favorites/${id}`, { method: "DELETE" });

// ── Alerts ──────────────────────────────────────────────────────────────────
export interface AlertConfig {
  id: number;
  scope_type: string;
  product_id: number | null;
  catalog_id: number | null;
  set_code: string | null;
  game: string | null;
  language: string | null;
  channel: "email" | "discord";
  destination: string;
  alert_type: "restock" | "price_drop" | "any";
  price_threshold: number | null;
  active: boolean;
  created_at: string;
}

export type AlertCreate = Omit<AlertConfig, "id" | "active" | "created_at">;

export const listAlerts = () => request<AlertConfig[]>("/alerts");
export const createAlert = (body: Partial<AlertCreate>) =>
  request<AlertConfig>("/alerts", { method: "POST", body: JSON.stringify(body) });
export const deleteAlert = (id: number) =>
  request<void>(`/alerts/${id}`, { method: "DELETE" });
export const testAlert = (id: number) =>
  request<{ success: boolean; detail: string }>(`/alerts/${id}/test`, { method: "POST" });

// ── Waitlist ────────────────────────────────────────────────────────────────
export interface WaitlistJoined {
  ok: boolean;
  message: string;
}

/** Inscription à la liste d'attente (endpoint public, rate-limité côté API).
 *  Idempotent : une adresse déjà inscrite renvoie le même message de succès. */
export const joinWaitlist = (email: string, source = "landing") =>
  request<WaitlistJoined>("/waitlist", {
    method: "POST",
    body: JSON.stringify({ email, source }),
  });
