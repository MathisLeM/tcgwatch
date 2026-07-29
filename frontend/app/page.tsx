import Image from "next/image";
import LandingNav from "@/components/LandingNav";
import { BRAND, SITE_URL } from "@/lib/brand";

const FEATURES = [
  {
    icon: "🔔",
    title: "Soyez le premier prévenu",
    desc: "Dès qu'un scellé revient en stock ou baisse de prix, l'alerte part aussitôt — e-mail, Discord ou Slack. Sur les boutiques à stock très limité, quelques minutes d'avance font toute la différence.",
  },
  {
    icon: "⏱️",
    title: "Scans fréquents",
    desc: "Selon votre formule, le marché est rescanné chaque semaine, chaque jour ou chaque heure. Plus le scan est fréquent, plus vous êtes alerté tôt — et premier sur la file.",
  },
  {
    icon: "🏪",
    title: "100+ boutiques françaises suivies",
    desc: "Nous surveillons automatiquement 100+ revendeurs français, des grandes enseignes aux petites boutiques spécialisées. Tout le marché au même endroit : qui a quoi, à quel prix officiel.",
  },
  {
    icon: "🎮",
    title: "Plusieurs jeux",
    desc: "Pokémon, One Piece et d'autres TCG — un seul outil pour surveiller tous vos produits scellés, sans jongler entre vingt sites.",
  },
  {
    icon: "📦",
    title: "Tous les types de scellés",
    desc: "Displays, coffrets dresseur d'élite, coffrets, bundles, blisters, tri/duo-packs, mini-tins et boosters — classés automatiquement, cartes à l'unité exclues.",
  },
  {
    icon: "🌍",
    title: "Multi-langues",
    desc: "Suivez les éditions française, anglaise, japonaise, coréenne et chinoise côte à côte. Filtrez exactement la langue que vous collectionnez.",
  },
  {
    icon: "🗂️",
    title: "Classé par bloc & série",
    desc: "Naviguez visuellement par bloc — Méga-Évolution, Écarlate et Violet, Épée et Bouclier — puis explorez chaque série avec son visuel et son code officiel.",
  },
  {
    icon: "💎",
    title: "Anciennes séries épuisées aussi suivies",
    desc: "On surveille aussi les scellés de séries plus anciennes, non rééditées et épuisées en boutique — forcément vendues au-dessus du prix de sortie. Comparez les tarifs des boutiques TCG spécialisées qu'on suit avec ceux de Cardmarket ou eBay, et complétez vos vieilles séries au meilleur prix.",
  },
  {
    icon: "🤝",
    title: "Construit avec la communauté",
    desc: "Vous connaissez une boutique mal couverte ? Proposez-la : si elle est compatible, on l'ajoute — et on vous offre un mois d'accès.",
  },
];

const STEPS = [
  {
    number: "01",
    title: "Choisissez ce que vous surveillez",
    desc: "Ajoutez les articles, séries ou langues qui vous intéressent à votre liste de surveillance — selon votre formule.",
  },
  {
    number: "02",
    title: "On scanne les boutiques",
    desc: "Selon votre formule, nous récupérons le stock et les prix en direct de 100+ revendeurs français et associons chaque annonce à sa série.",
  },
  {
    number: "03",
    title: "Vous êtes alerté",
    desc: "Réappro, baisse de prix, nouveau produit ? Une alerte arrive dans votre boîte mail ou sur Discord à l'instant où ça se produit.",
  },
  {
    number: "04",
    title: "Achetez au prix officiel",
    desc: "Accédez directement à l'annonce en stock la moins chère et attrapez-la avant les scalpers.",
  },
];

const PERSONAS = [
  {
    icon: "🃏",
    persona: "Collectionneurs",
    text: "Complétez votre collection au prix boutique. Soyez prévenu dès qu'un display manquant réapparaît — avant qu'un scalper ne le rafle.",
  },
  {
    icon: "🎮",
    persona: "Joueurs",
    text: "Trouvez vos boosters et displays pour jouer sans payer le double sur eBay. Le bon produit, au bon prix, au bon moment.",
  },
  {
    icon: "👪",
    persona: "Parents & familles",
    text: "Offrez le cadeau parfait sans tomber sur une arnaque à prix gonflé — on vous montre où c'est disponible au tarif officiel.",
  },
];

const BLOCKS = [
  { code: "ME", sets: "5 séries", img: "/images/blocks/bloc-mega-evolution.png" },
  { code: "EV", sets: "12 séries", img: "/images/blocks/bloc-ecarlate-et-violet.jpg" },
  { code: "EB", sets: "14 séries", img: "/images/blocks/bloc-epee-et-bouclier.jpg" },
];

const SERIES_CARDS = [
  { code: "PRE", kind: "Display", price: "164,90 €", status: "in", img: "/images/series/serie_evolutions_prismatiques.jpg" },
  { code: "CRI", kind: "Coffret Élite", price: "59,90 €", status: "drop", img: "/images/series/serie_chaos_ascendant.jpg" },
  { code: "OBF", kind: "Display", price: "—", status: "out", img: "/images/series/serie_flammes_obsidiennes.jpg" },
  { code: "SSP", kind: "Coffret", price: "44,90 €", status: "in", img: "/images/series/serie_etincelles_deferlantes.jpg" },
];

const PLANS = [
  {
    name: "Bronze",
    accent: "text-amber-700",
    ring: "border-gray-800",
    price: "Gratuit",
    items: "1 article suivi",
    refresh: "Scan hebdomadaire",
    highlight: false,
    perks: [
      "Alertes par e-mail",
      "Navigation par bloc & série",
      "Multi-langues & multi-jeux",
      "Anciennes séries épuisées incluses",
    ],
  },
  {
    name: "Silver",
    accent: "text-gray-300",
    ring: "border-gray-700",
    price: "7,99 €",
    items: "10 articles ou 1 set",
    refresh: "Scan quotidien",
    highlight: false,
    perks: [
      "Alertes e-mail + Discord",
      "Historique des prix & du stock",
      "Comparaison avec les grandes plateformes",
      "Filtres avancés & recherche",
    ],
  },
  {
    name: "Gold",
    accent: "text-amber-400",
    ring: "border-amber-500/60",
    price: "14,99 €",
    items: "Articles illimités",
    refresh: "Scan toutes les heures",
    highlight: true,
    perks: [
      "Alertes instantanées e-mail + Discord + Slack",
      "Priorité sur les réappros à stock limité",
      "Le plus de chances d'être le premier",
      "Toutes les fonctionnalités",
    ],
  },
];

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: BRAND,
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "Alertes stock et prix pour les produits scellés Pokémon, One Piece et plus, sur 100+ boutiques françaises. Par des passionnés, contre les scalpers.",
  url: SITE_URL,
};

function StatusBadge({ status }: { status: string }) {
  const cfg =
    status === "in"
      ? "text-emerald-400 bg-emerald-950/60 border-emerald-800/60"
      : status === "drop"
      ? "text-amber-400 bg-amber-950/60 border-amber-800/60"
      : "text-gray-400 bg-gray-900/80 border-gray-700/60";
  const label = status === "in" ? "🟢 En stock" : status === "drop" ? "🔻 Baisse" : "⚪ Rupture";
  return (
    <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full border whitespace-nowrap ${cfg}`}>
      {label}
    </span>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <LandingNav />

      {/* ── Hero ── */}
      <section className="pt-36 pb-24 px-6 text-center relative overflow-hidden">
        <div className="absolute inset-0 -z-10">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[450px]
                          bg-red-600/10 blur-[140px] rounded-full" />
        </div>

        <div className="max-w-3xl mx-auto space-y-6">
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <span className="inline-flex items-center gap-2 text-xs font-medium text-red-300
                            border border-red-800/70 bg-red-950/40 px-3 py-1.5 rounded-full">
              🛡️ Par des passionnés, contre les scalpers
            </span>
            <span className="inline-flex items-center gap-2 text-xs font-medium text-amber-400
                            border border-amber-800/70 bg-amber-950/40 px-3 py-1.5 rounded-full">
              🤝 Outil communautaire
            </span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold tracking-tight text-white leading-tight">
            Achetez vos scellés au{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-red-400 to-amber-400">
              prix boutique
            </span>
            , avant les scalpers
          </h1>

          <p className="text-lg text-gray-400 max-w-xl mx-auto leading-relaxed">
            {BRAND} surveille 100+ boutiques françaises et vous alerte dès qu&apos;un
            scellé Pokémon ou One Piece est réapprovisionné ou baisse de prix — pour
            l&apos;acheter au tarif officiel, sans payer les prix gonflés d&apos;eBay
            ou Cardmarket.
          </p>

          <div className="flex items-center justify-center gap-4 pt-2">
            <a
              href="#waitlist"
              className="bg-red-600 hover:bg-red-500 text-white font-semibold
                         px-6 py-3 rounded-xl transition-colors text-sm"
            >
              Rejoindre la liste d&apos;attente
            </a>
            <a
              href="#pricing"
              className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1"
            >
              Voir les formules ↓
            </a>
          </div>
        </div>

        {/* Aperçu produit */}
        <div className="mt-20 max-w-4xl mx-auto">
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-2xl shadow-black/40">
            <div className="border-b border-gray-800 px-4 py-3 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500/60" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/60" />
              <div className="w-3 h-3 rounded-full bg-green-500/60" />
              <span className="ml-3 text-xs text-gray-600 font-mono">{BRAND.toLowerCase()}.app/series</span>
            </div>
            <div className="p-6 space-y-5 text-left">
              {/* blocs — visuels rectangulaires standardisés (image entière) */}
              <div>
                <p className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Blocs</p>
                <div className="grid grid-cols-3 gap-3">
                  {BLOCKS.map(({ code, sets, img }) => (
                    <div key={code} className="bg-gray-800/60 border border-gray-700/50 rounded-xl p-2">
                      <div className="relative w-full aspect-[16/10] rounded-md overflow-hidden bg-gray-950/40">
                        <Image src={img} alt={code} fill sizes="(max-width:768px) 33vw, 220px" className="object-contain" />
                      </div>
                      <div className="px-1 pt-1.5 flex items-center justify-between">
                        <span className="text-xs text-red-400 font-mono font-semibold">{code}</span>
                        <span className="text-[11px] text-gray-500">{sets}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* séries — mêmes cartes rectangulaires, code conservé, nom dans l'image */}
              <div>
                <p className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Séries</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {SERIES_CARDS.map(({ code, kind, price, status, img }) => (
                    <div key={code} className="bg-gray-800/50 border border-gray-700/40 rounded-xl p-2">
                      <div className="relative w-full aspect-[16/10] rounded-md overflow-hidden bg-gray-950/40">
                        <Image src={img} alt={code} fill sizes="(max-width:768px) 50vw, 200px" className="object-contain" />
                        <span className="absolute top-1 left-1 text-[9px] font-mono font-semibold text-amber-300
                                         bg-gray-950/80 px-1.5 py-0.5 rounded">
                          {code}
                        </span>
                        <span className="absolute top-1 right-1">
                          <StatusBadge status={status} />
                        </span>
                      </div>
                      <div className="px-1 pt-1.5 flex items-center justify-between">
                        <span className="text-[11px] text-gray-500">{kind}</span>
                        <span className="text-xs font-bold text-white">{price}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 text-[10px] font-medium text-amber-400
                                 border border-amber-800/60 bg-amber-950/40 px-2.5 py-1 rounded-full">
                  <span className="w-1 h-1 bg-amber-400 rounded-full" />
                  Scan auto · dernier passage il y a 18 min
                </span>
                <span className="inline-flex items-center gap-1.5 text-[10px] font-medium text-emerald-400
                                 border border-emerald-800/60 bg-emerald-950/40 px-2.5 py-1 rounded-full">
                  E-mail ✓ · Discord ✓
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Manifeste anti-scalper ── */}
      <section id="manifesto" className="py-20 px-6 border-t border-gray-800/60">
        <div className="max-w-5xl mx-auto grid md:grid-cols-2 gap-10 items-center">
          <div className="space-y-5">
            <h2 className="text-3xl font-bold text-white leading-tight">
              Des passionnés. Pas des scalpers.
            </h2>
            <p className="text-gray-400 leading-relaxed">
              Les éditions limitées partent en quelques minutes — rachetées en masse
              pour être revendues bien plus cher sur eBay ou Cardmarket. {BRAND} remet
              les passionnés en première ligne&nbsp;: on vous prévient dès qu&apos;un
              produit est disponible en boutique, au prix officiel, pour que vous
              l&apos;achetiez <span className="text-white font-medium">avant</span> les
              revendeurs — pas après, au prix fort.
            </p>
            <p className="text-sm text-gray-500">
              Pas un outil de revente : un outil pour que la communauté paie le juste prix.
            </p>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-3">
            <p className="text-xs text-gray-500 mb-2">Un même display, deux mondes&nbsp;:</p>
            <div className="flex items-center justify-between bg-emerald-950/30 border border-emerald-900/50 rounded-xl px-4 py-3">
              <span className="text-sm text-gray-300">🏪 En boutique, avec {BRAND}</span>
              <span className="text-lg font-bold text-emerald-400">59,90 €</span>
            </div>
            <div className="flex items-center justify-between bg-red-950/30 border border-red-900/50 rounded-xl px-4 py-3">
              <span className="text-sm text-gray-300">📈 Chez un scalper (eBay / Cardmarket)</span>
              <span className="text-lg font-bold text-red-400">≈ 119 €</span>
            </div>
            <p className="text-center text-xs text-gray-500 pt-1">
              Jusqu&apos;à <span className="text-red-400 font-semibold">+100 %</span> de plus.
              Soyez là au bon moment.
            </p>
          </div>
        </div>
      </section>

      {/* ── Fonctionnalités ── */}
      <section id="features" className="py-24 px-6 border-t border-gray-800/60">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-white mb-3">
              Tout le marché français, surveillé pour vous
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto">
              {BRAND} suit le stock et les prix des TCG scellés à votre place, pour que
              vous achetiez au tarif officiel sans courir vingt sites.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {FEATURES.map(({ icon, title, desc }) => (
              <div
                key={title}
                className="bg-gray-900 border border-gray-800 rounded-2xl p-6
                           hover:border-gray-700 transition-colors"
              >
                <div className="text-2xl mb-4">{icon}</div>
                <h3 className="text-white font-semibold mb-2">{title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comment ça marche ── */}
      <section id="how-it-works" className="py-24 px-6 border-t border-gray-800/60">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-white mb-3">Comment ça marche</h2>
            <p className="text-gray-400">De votre liste de surveillance à l&apos;achat au prix officiel, en quatre étapes.</p>
          </div>

          <div className="grid md:grid-cols-4 gap-8 relative">
            <div className="hidden md:block absolute top-8 left-[12.5%] right-[12.5%] h-px bg-gradient-to-r from-red-800/0 via-red-700/50 to-red-800/0" />
            {STEPS.map(({ number, title, desc }) => (
              <div key={number} className="relative text-center space-y-3">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl
                                bg-red-950 border border-red-800 text-red-400
                                font-bold text-lg mx-auto">
                  {number}
                </div>
                <h3 className="text-white font-semibold">{title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Communauté ── */}
      <section id="community" className="py-24 px-6 border-t border-gray-800/60">
        <div className="max-w-5xl mx-auto">
          <div className="bg-gradient-to-br from-red-950/40 to-amber-950/20 border border-red-900/50 rounded-3xl p-10 md:p-14">
            <div className="grid md:grid-cols-2 gap-10 items-center">
              <div className="space-y-5">
                <span className="inline-flex items-center gap-2 text-xs font-medium text-red-300
                                border border-red-800/70 bg-red-950/50 px-3 py-1.5 rounded-full">
                  🤝 Une communauté de passionnés
                </span>
                <h2 className="text-3xl font-bold text-white leading-tight">
                  Vous connaissez une boutique qu&apos;on ne suit pas encore&nbsp;?
                </h2>
                <p className="text-gray-300 leading-relaxed">
                  {BRAND} grandit grâce à sa communauté. Proposez un site avec des
                  produits scellés peu ou pas listés chez nous — s&apos;il est
                  compatible avec nos scrapers et qu&apos;on l&apos;ajoute, on vous
                  offre <span className="text-amber-400 font-semibold">1 mois d&apos;accès</span> en
                  remerciement.
                </p>
                <p className="text-sm text-gray-500">
                  Plus la communauté contribue, plus on couvre le marché — et plus on
                  garde une longueur d&apos;avance sur les scalpers.
                </p>
              </div>

              <div className="space-y-3">
                {[
                  { step: "1", text: "Repérez une boutique avec du scellé mal couvert chez nous." },
                  { step: "2", text: "Proposez-la en un clic depuis votre espace (ou par e-mail)." },
                  { step: "3", text: "Si elle est compatible et ajoutée : 1 mois offert." },
                ].map(({ step, text }) => (
                  <div key={step} className="flex items-start gap-3 bg-gray-900/60 border border-gray-800 rounded-xl p-4">
                    <span className="flex items-center justify-center w-7 h-7 rounded-full bg-red-900/60 border border-red-700 text-red-300 text-sm font-bold shrink-0">
                      {step}
                    </span>
                    <p className="text-sm text-gray-300 leading-relaxed">{text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Tarifs ── */}
      <section id="pricing" className="py-24 px-6 border-t border-gray-800/60">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-white mb-3">Des formules simples</h2>
            <p className="text-gray-400 max-w-2xl mx-auto">
              Deux leviers à parts égales&nbsp;: <span className="text-white font-medium">combien
              d&apos;articles</span> vous suivez, et <span className="text-white font-medium">à
              quelle fréquence</span> on scanne le marché. Plus c&apos;est fréquent, plus vous
              êtes prévenu tôt — décisif sur les boutiques à stock très limité, où tout part en
              quelques minutes.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 items-stretch">
            {PLANS.map(({ name, accent, ring, price, items, refresh, perks, highlight }) => (
              <div
                key={name}
                className={
                  "relative bg-gray-900 border rounded-2xl p-7 flex flex-col " +
                  (highlight ? "border-amber-500/60 shadow-xl shadow-amber-950/20" : ring)
                }
              >
                {highlight && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[11px] font-semibold
                                   text-gray-950 bg-amber-400 px-3 py-1 rounded-full">
                    Le plus populaire
                  </span>
                )}
                <h3 className={`text-lg font-bold ${accent}`}>{name}</h3>
                <div className="mt-3 mb-4 flex items-end gap-1">
                  <span className="text-3xl font-bold text-white">{price}</span>
                  {price !== "Gratuit" && <span className="text-sm text-gray-500 mb-1">/mois</span>}
                </div>
                {/* Les deux axes mis sur un pied d'égalité : combien de suivi, et à quelle fréquence */}
                <div className="grid grid-cols-2 gap-2 mb-5">
                  <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2.5 text-center">
                    <p className="text-[10px] text-gray-500 mb-0.5">📦 Articles suivis</p>
                    <p className="text-xs font-bold text-white leading-tight">{items}</p>
                  </div>
                  <div className="bg-gray-800/60 border border-gray-700/50 rounded-lg p-2.5 text-center">
                    <p className="text-[10px] text-gray-500 mb-0.5">⏱️ Rafraîchissement</p>
                    <p className="text-xs font-bold text-amber-400 leading-tight">{refresh}</p>
                  </div>
                </div>
                <ul className="space-y-2.5 flex-1">
                  {perks.map((perk) => (
                    <li key={perk} className="flex items-start gap-2 text-sm text-gray-300">
                      <span className="text-emerald-400 mt-0.5">✓</span>
                      <span>{perk}</span>
                    </li>
                  ))}
                </ul>
                <a
                  href="#waitlist"
                  className={
                    "mt-6 text-center font-semibold px-5 py-2.5 rounded-xl transition-colors text-sm " +
                    (highlight
                      ? "bg-amber-500 hover:bg-amber-400 text-gray-950"
                      : "bg-gray-800 hover:bg-gray-700 text-white")
                  }
                >
                  Choisir {name}
                </a>
              </div>
            ))}
          </div>

          {/* Bandeau communautaire */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3 text-center
                          bg-red-950/30 border border-red-900/50 rounded-2xl px-6 py-4">
            <span className="text-lg">🤝</span>
            <p className="text-sm text-gray-300">
              <span className="font-semibold text-white">Contribuez, c&apos;est gratuit&nbsp;:</span>{" "}
              proposez une boutique compatible avec des produits peu listés et recevez{" "}
              <span className="text-amber-400 font-semibold">1 mois de Gold offert</span>.
            </p>
          </div>

          <p className="text-center text-xs text-gray-600 mt-6">
            Tarifs indicatifs — la facturation et les abonnements arrivent au lancement.
          </p>
        </div>
      </section>

      {/* ── Personas ── */}
      <section className="py-16 px-6 border-t border-gray-800/60">
        <div className="max-w-4xl mx-auto">
          <div className="grid md:grid-cols-3 gap-6">
            {PERSONAS.map(({ persona, icon, text }) => (
              <div key={persona} className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 space-y-3">
                <div className="text-2xl">{icon}</div>
                <h3 className="text-white font-semibold">{persona}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Liste d'attente ── */}
      <section className="py-24 px-6 border-t border-gray-800/60">
        <div id="waitlist" className="max-w-2xl mx-auto text-center space-y-6">
          <h2 className="text-3xl font-bold text-white">
            Rejoignez la communauté {BRAND}.
          </h2>
          <p className="text-gray-400">
            Nous ouvrons bientôt l&apos;accès anticipé — alertes personnalisées, suivi
            d&apos;articles et formules d&apos;abonnement. Laissez votre e-mail et on vous prévient.
          </p>
          <form
            className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-md mx-auto"
            action="#"
          >
            <input
              type="email"
              required
              placeholder="vous@exemple.com"
              className="w-full sm:flex-1 bg-gray-900 border border-gray-700 rounded-xl
                         px-4 py-3 text-sm text-white placeholder-gray-500
                         focus:outline-none focus:border-red-500"
            />
            <button
              type="submit"
              className="bg-red-600 hover:bg-red-500 text-white font-semibold
                         px-6 py-3 rounded-xl transition-colors text-sm whitespace-nowrap"
            >
              Prévenez-moi →
            </button>
          </form>
          <p className="text-xs text-gray-600 pt-2">
            Pas de spam — juste un e-mail à l&apos;ouverture.
          </p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-gray-800/60 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>🎴</span>
            <span className="font-semibold text-gray-500">{BRAND}</span>
            <span>— la communauté qui achète au prix boutique</span>
          </div>
          <div className="flex items-center gap-6 text-xs text-gray-600">
            <a href="#features" className="hover:text-gray-400 transition-colors">Fonctionnalités</a>
            <a href="#community" className="hover:text-gray-400 transition-colors">Communauté</a>
            <a href="#pricing" className="hover:text-gray-400 transition-colors">Tarifs</a>
            <a href="#waitlist" className="hover:text-gray-400 transition-colors">Liste d&apos;attente</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
