import Link from "next/link";
import { BRAND } from "@/lib/brand";

export default function LandingNav() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-gray-950/80 backdrop-blur-md">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 font-bold text-white text-lg">
          <span className="text-xl">🎴</span>
          {BRAND}
        </Link>

        {/* Nav links */}
        <nav className="hidden md:flex items-center gap-6 text-sm text-gray-400">
          <a href="#features" className="hover:text-white transition-colors">Fonctionnalités</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">Comment ça marche</a>
          <a href="#community" className="hover:text-white transition-colors">Communauté</a>
          <a href="#pricing" className="hover:text-white transition-colors">Tarifs</a>
        </nav>

        {/* CTA */}
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm text-gray-300 hover:text-white transition-colors">
            Connexion
          </Link>
          <Link
            href="/login?mode=signup"
            className="bg-red-600 hover:bg-red-500 text-white text-sm font-semibold
                       px-4 py-2 rounded-lg transition-colors"
          >
            S&apos;inscrire
          </Link>
        </div>
      </div>
    </header>
  );
}
