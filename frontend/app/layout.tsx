import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { BRAND, TAGLINE, SITE_URL } from "@/lib/brand";
import { AuthProvider } from "@/lib/auth";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });

const title = `${BRAND} — ${TAGLINE}`;
const description =
  "Suivez les produits scellés Pokémon, One Piece et plus sur 100+ boutiques françaises. " +
  "Recevez une alerte dès qu'un produit est réapprovisionné ou baisse de prix, organisé par bloc et série.";

export const metadata: Metadata = {
  title,
  description,
  metadataBase: new URL(SITE_URL),
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  openGraph: {
    title,
    description,
    url: SITE_URL,
    siteName: BRAND,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={`${geist.variable} antialiased bg-gray-950 text-gray-100 min-h-screen`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
