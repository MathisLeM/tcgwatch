"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { BRAND } from "@/lib/brand";

// Alpha: public signup is closed (accounts are provisioned by an admin). Set
// NEXT_PUBLIC_ALLOW_SIGNUP=true to show the "create account" flow again.
const ALLOW_SIGNUP = process.env.NEXT_PUBLIC_ALLOW_SIGNUP === "true";

function AuthForm() {
  const { login, signup } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = useState<"login" | "signup">(
    ALLOW_SIGNUP && params.get("mode") === "signup" ? "signup" : "login"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "signup") await signup(email, password);
      else await login(email, password);
      router.push("/catalog");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <Link href="/" className="flex items-center justify-center gap-2 font-bold text-xl mb-8">
          <span>🎴</span> {BRAND}
        </Link>
        <div className="bg-panel border border-line-strong rounded-2xl p-6">
          <h1 className="text-lg font-semibold mb-1">
            {mode === "signup" ? "Créer un compte" : "Connexion"}
          </h1>
          <p className="text-sm text-muted mb-5">
            {mode === "signup"
              ? "Suivez vos produits et recevez des alertes de réapprovisionnement."
              : ALLOW_SIGNUP
                ? "Accédez à votre dashboard et vos favoris."
                : "Alpha privée — connectez-vous avec les identifiants qui vous ont été communiqués."}
          </p>
          <form onSubmit={onSubmit} className="space-y-3">
            <input
              type="text" required autoComplete="username"
              placeholder="Identifiant (pseudo ou email)" value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg bg-canvas border border-line-strong px-3 py-2 text-sm
                         focus:outline-none focus:border-accent"
            />
            <input
              type="password" required placeholder="Mot de passe (8+ caractères)" value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg bg-canvas border border-line-strong px-3 py-2 text-sm
                         focus:outline-none focus:border-accent"
            />
            {error && <p className="text-sm text-accent">{error}</p>}
            <button
              type="submit" disabled={busy}
              className="w-full bg-accent hover:brightness-110 disabled:opacity-60 text-on-accent
                         text-sm font-semibold py-2 rounded-lg transition-colors"
            >
              {busy ? "…" : mode === "signup" ? "Créer mon compte" : "Se connecter"}
            </button>
          </form>
          {ALLOW_SIGNUP && (
            <button
              onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setError(null); }}
              className="mt-4 text-sm text-muted hover:text-ink transition-colors w-full text-center"
            >
              {mode === "signup"
                ? "Déjà un compte ? Se connecter"
                : "Pas encore de compte ? S'inscrire"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <AuthForm />
    </Suspense>
  );
}
