import type { Metadata } from "next";
import { Bricolage_Grotesque, Geist } from "next/font/google";
import "./globals.css";
import { BRAND, TAGLINE, SITE_URL } from "@/lib/brand";
import { AuthProvider } from "@/lib/auth";

const geist = Geist({ variable: "--font-geist", subsets: ["latin"] });
// Police d'affichage des titres (landing v2)
const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
});

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
      <body
        className={`${geist.variable} ${bricolage.variable} antialiased bg-canvas text-ink min-h-screen`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
