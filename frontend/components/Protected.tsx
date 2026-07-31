"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import AppNav from "./AppNav";

/** Wraps an app page: redirects to /login when not authenticated, renders the nav otherwise. */
export default function Protected({ children }: { children: React.ReactNode }) {
  const { loaded, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loaded && !isAuthenticated) router.replace("/login");
  }, [loaded, isAuthenticated, router]);

  if (!loaded) {
    return <div className="min-h-screen flex items-center justify-center text-dim">Chargement…</div>;
  }
  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <AppNav />
      <main className="max-w-[1280px] mx-auto p-[clamp(16px,3vw,24px)]">{children}</main>
    </div>
  );
}
