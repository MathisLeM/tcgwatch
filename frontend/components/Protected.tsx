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
    return <div className="min-h-screen flex items-center justify-center text-gray-500">Chargement…</div>;
  }
  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen">
      <AppNav />
      <main className="max-w-7xl mx-auto px-6 py-6">{children}</main>
    </div>
  );
}
