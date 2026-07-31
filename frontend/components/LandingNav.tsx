"use client";

import Link from "next/link";
import { useState } from "react";
import { BRAND } from "@/lib/brand";
import Icon from "@/components/Icons";

const LINKS = [
  { href: "#features", label: "Fonctionnalités" },
  { href: "#how-it-works", label: "Comment ça marche" },
  { href: "#community", label: "Communauté" },
  { href: "#pricing", label: "Tarifs" },
];

export default function LandingNav() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      className="sticky top-0 z-50 border-b border-line
                 bg-[color-mix(in_srgb,var(--color-canvas)_82%,transparent)] backdrop-blur-[14px]"
    >
      <div className="max-w-[1160px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5 text-ink">
          <span className="flex items-center justify-center w-8 h-8 rounded-[9px] bg-accent text-on-accent">
            <Icon name="cards" size={17} strokeWidth={2} />
          </span>
          <span className="font-display font-bold text-lg tracking-[-0.01em]">{BRAND}</span>
        </Link>

        {/* Desktop */}
        <nav className="hidden md:flex items-center gap-[26px] text-sm">
          {LINKS.map(({ href, label }) => (
            <a key={href} href={href} className="text-muted hover:text-ink transition-colors">
              {label}
            </a>
          ))}
        </nav>
        <div className="hidden md:flex items-center gap-3.5">
          <Link href="/login" className="text-sm text-ink hover:text-muted transition-colors">
            Connexion
          </Link>
          <Link
            href="/login?mode=signup"
            className="bg-accent text-on-accent text-sm font-semibold px-4 py-2.5 rounded-[10px]
                       hover:brightness-110 transition-[filter]"
          >
            S&apos;inscrire
          </Link>
        </div>

        {/* Mobile */}
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-label="Menu"
          aria-expanded={menuOpen}
          aria-controls="landing-mobile-menu"
          className="md:hidden w-[42px] h-[42px] rounded-[10px] bg-panel border border-line-strong
                     text-ink flex items-center justify-center cursor-pointer"
        >
          <Icon name={menuOpen ? "close" : "menu"} strokeWidth={2} />
        </button>
      </div>

      {menuOpen && (
        <nav
          id="landing-mobile-menu"
          className="md:hidden flex flex-col gap-1 px-4 sm:px-6 pt-3 pb-4.5 border-t border-line bg-canvas"
        >
          {LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              onClick={() => setMenuOpen(false)}
              className="px-2.5 py-3 rounded-[10px] text-base text-muted hover:bg-panel hover:text-ink transition-colors"
            >
              {label}
            </a>
          ))}
          <div className="flex gap-2.5 mt-2.5">
            <Link
              href="/login"
              onClick={() => setMenuOpen(false)}
              className="flex-1 text-center border border-line-strong text-ink text-sm font-semibold py-3 rounded-[10px]"
            >
              Connexion
            </Link>
            <Link
              href="/login?mode=signup"
              onClick={() => setMenuOpen(false)}
              className="flex-1 text-center bg-accent text-on-accent text-sm font-semibold py-3 rounded-[10px]"
            >
              S&apos;inscrire
            </Link>
          </div>
        </nav>
      )}
    </header>
  );
}
