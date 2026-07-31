"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { BRAND } from "@/lib/brand";
import Icon from "@/components/Icons";

const LINKS = [
  { href: "/catalog", label: "Catalogue" },
  { href: "/dashboard", label: "Produits" },
  { href: "/trends", label: "Tendances" },
  { href: "/favorites", label: "Favoris" },
  { href: "/alerts", label: "Alertes" },
];

export default function AppNav() {
  const { email, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  return (
    <header
      className="sticky top-0 z-50 border-b border-line
                 bg-[color-mix(in_srgb,var(--color-canvas)_84%,transparent)] backdrop-blur-[14px]"
    >
      <div className="max-w-[1280px] mx-auto px-[clamp(14px,3vw,24px)] h-15 flex items-center justify-between gap-4">
        <div className="flex items-center gap-[26px] min-w-0">
          <Link href="/catalog" className="flex items-center gap-2.5 text-ink">
            <span className="flex items-center justify-center w-[30px] h-[30px] rounded-lg bg-accent text-on-accent">
              <Icon name="cards" size={16} strokeWidth={2} />
            </span>
            <span className="font-display font-bold text-[17px] tracking-[-0.01em]">{BRAND}</span>
          </Link>

          {/* Desktop */}
          <nav className="hidden wide:flex items-center gap-1 text-sm">
            {LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                aria-current={pathname === href ? "page" : undefined}
                className={`px-3 py-1.5 rounded-[9px] transition-colors ${
                  pathname === href
                    ? "bg-accent-soft text-accent font-semibold"
                    : "text-muted hover:bg-panel hover:text-ink"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="hidden wide:inline text-xs text-dim">{email}</span>
          <button
            type="button"
            onClick={async () => {
              await logout();
              router.push("/");
            }}
            className="flex items-center gap-[7px] text-[13px] text-muted bg-panel border border-line-strong
                       px-3 py-1.5 rounded-[9px] cursor-pointer hover:text-ink hover:border-dim transition-colors"
          >
            <Icon name="logout" size={14} strokeWidth={2} />
            Déconnexion
          </button>
        </div>
      </div>

      {/* Mobile — pills that scroll horizontally rather than a burger, so the
          current section stays visible one tap away. */}
      <nav className="wide:hidden flex gap-1.5 px-3.5 pb-2.5 overflow-x-auto text-[13px]">
        {LINKS.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname === href ? "page" : undefined}
            className={`px-3 py-1.5 rounded-full whitespace-nowrap border ${
              pathname === href
                ? "bg-accent-soft border-accent-line text-accent font-semibold"
                : "bg-panel border-line text-muted"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
