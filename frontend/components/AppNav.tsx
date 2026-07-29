"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { BRAND } from "@/lib/brand";

export default function AppNav() {
  const { email, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const link = (href: string, label: string) => (
    <Link
      href={href}
      className={`text-sm transition-colors ${
        pathname === href ? "text-white font-medium" : "text-gray-400 hover:text-white"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <header className="sticky top-0 z-50 border-b border-white/5 bg-gray-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/catalog" className="flex items-center gap-2 font-bold text-lg">
            <span>🎴</span> {BRAND}
          </Link>
          <nav className="flex items-center gap-5">
            {link("/catalog", "Catalogue")}
            {link("/dashboard", "Produits")}
            {link("/favorites", "Favoris")}
            {link("/alerts", "Alertes")}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:inline text-xs text-gray-500">{email}</span>
          <button
            onClick={async () => { await logout(); router.push("/"); }}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </header>
  );
}
