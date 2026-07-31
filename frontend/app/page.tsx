import Image from "next/image";
import LandingNav from "@/components/LandingNav";
import Icon, { type IconName } from "@/components/Icons";
import { BRAND, SITE_URL } from "@/lib/brand";

/* Classes partagées — reprises de la maquette « Landing v2 ». */
const SECTION = "py-[clamp(56px,8vw,100px)] px-[clamp(16px,4vw,32px)] border-t border-line";
const SHELL = "max-w-[1160px] mx-auto";
const EYEBROW = "text-[13px] font-semibold tracking-[0.14em] uppercase text-accent";
const H2 = "font-display text-[clamp(28px,3.4vw,42px)] font-extrabold tracking-[-0.025em] leading-[1.12]";
const CARD = "bg-panel border border-line rounded-[18px] p-6 flex flex-col gap-3.5";
const ICON_TILE = "flex items-center justify-center w-[42px] h-[42px] rounded-xl";

const STATS = [
  { value: "100+", label: "boutiques françaises suivies", accent: false },
  { value: "8", label: "plateformes e-commerce scannées", accent: false },
  { value: "5", label: "langues d'édition suivies", accent: false },
  { value: "1 h", label: "entre deux scans en formule Gold", accent: true },
];

const FEATURES: { icon: IconName; title: string; desc: string }[] = [
  {
    icon: "bell",
    title: "Soyez le premier prévenu",
    desc: "Dès qu'un scellé revient en stock ou baisse de prix, l'alerte part aussitôt — e-mail, Discord ou Slack. Sur les boutiques à stock très limité, quelques minutes d'avance font toute la différence.",
  },
  {
    icon: "timer",
    title: "Scans fréquents",
    desc: "Selon votre formule, le marché est rescanné chaque semaine, chaque jour ou chaque heure. Plus le scan est fréquent, plus vous êtes alerté tôt — et premier sur la file.",
  },
  {
    icon: "shop",
    title: "100+ boutiques françaises suivies",
    desc: "Nous surveillons automatiquement 100+ revendeurs français, des grandes enseignes aux petites boutiques spécialisées. Tout le marché au même endroit : qui a quoi, à quel prix officiel.",
  },
  {
    icon: "gamepad",
    title: "Plusieurs jeux",
    desc: "Pokémon, One Piece et d'autres TCG — un seul outil pour surveiller tous vos produits scellés, sans jongler entre vingt sites.",
  },
  {
    icon: "box",
    title: "Tous les types de scellés",
    desc: "Displays, coffrets dresseur d'élite, coffrets, bundles, blisters, tri/duo-packs, mini-tins et boosters — classés automatiquement, cartes à l'unité exclues.",
  },
  {
    icon: "globe",
    title: "Multi-langues",
    desc: "Suivez les éditions française, anglaise, japonaise, coréenne et chinoise côte à côte. Filtrez exactement la langue que vous collectionnez.",
  },
  {
    icon: "layers",
    title: "Classé par bloc & série",
    desc: "Naviguez visuellement par bloc — Méga-Évolution, Écarlate et Violet, Épée et Bouclier — puis explorez chaque série avec son visuel et son code officiel.",
  },
  {
    icon: "gem",
    title: "Anciennes séries épuisées aussi suivies",
    desc: "On surveille aussi les scellés de séries non rééditées et épuisées en boutique. Comparez les tarifs des boutiques spécialisées avec Cardmarket ou eBay, et complétez vos vieilles séries au meilleur prix.",
  },
  {
    icon: "users",
    title: "Construit avec la communauté",
    desc: "Vous connaissez une boutique mal couverte ? Proposez-la : si elle est compatible, on l'ajoute — et on vous offre un mois d'accès.",
  },
];

const STEPS: { number: string; icon: IconName; title: string; desc: string; ok?: boolean }[] = [
  {
    number: "01",
    icon: "eye",
    title: "Choisissez ce que vous surveillez",
    desc: "Ajoutez les articles, séries ou langues qui vous intéressent à votre liste de surveillance — selon votre formule.",
  },
  {
    number: "02",
    icon: "search",
    title: "On scanne les boutiques",
    desc: "Nous récupérons le stock et les prix en direct de 100+ revendeurs français et associons chaque annonce à sa série.",
  },
  {
    number: "03",
    icon: "bell",
    title: "Vous êtes alerté",
    desc: "Réappro, baisse de prix, nouveau produit ? Une alerte arrive par e-mail ou sur Discord à l'instant où ça se produit.",
  },
  {
    number: "04",
    icon: "cart",
    title: "Achetez au prix officiel",
    desc: "Accédez directement à l'annonce en stock la moins chère et attrapez-la avant les scalpers.",
    ok: true,
  },
];

const CONTRIBUTION_STEPS = [
  { step: "1", text: "Repérez une boutique avec du scellé mal couvert chez nous.", gold: false },
  { step: "2", text: "Proposez-la en un clic depuis votre espace (ou par e-mail).", gold: false },
  { step: "3", text: "Si elle est compatible et ajoutée : 1 mois offert.", gold: true },
];

const PLANS = [
  {
    name: "Bronze",
    nameClass: "text-[#C9853E]",
    price: "Gratuit",
    period: false,
    items: "1 article",
    refresh: "Hebdomadaire",
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
    nameClass: "text-[#B8C2CC]",
    price: "7,99 €",
    period: true,
    items: "10 ou 1 set",
    refresh: "Quotidienne",
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
    nameClass: "text-gold",
    price: "14,99 €",
    period: true,
    items: "Illimités",
    refresh: "Toutes les heures",
    highlight: true,
    perks: [
      "Alertes instantanées e-mail + Discord + Slack",
      "Priorité sur les réappros à stock limité",
      "Le plus de chances d'être le premier",
      "Toutes les fonctionnalités",
    ],
  },
];

const PERSONAS: { icon: IconName; title: string; desc: string }[] = [
  {
    icon: "gem",
    title: "Collectionneurs",
    desc: "Complétez votre collection au prix boutique. Soyez prévenu dès qu'un display manquant réapparaît — avant qu'un scalper ne le rafle.",
  },
  {
    icon: "gamepad",
    title: "Joueurs",
    desc: "Trouvez vos boosters et displays pour jouer sans payer le double sur eBay. Le bon produit, au bon prix, au bon moment.",
  },
  {
    icon: "heart",
    title: "Parents & familles",
    desc: "Offrez le cadeau parfait sans tomber sur une arnaque à prix gonflé — on vous montre où c'est disponible au tarif officiel.",
  },
];

const FOOTER_LINKS = [
  { href: "#features", label: "Fonctionnalités" },
  { href: "#community", label: "Communauté" },
  { href: "#pricing", label: "Tarifs" },
  { href: "#waitlist", label: "Liste d'attente" },
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

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-canvas text-ink font-sans [overflow-x:clip]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <LandingNav />

      {/* ── Hero ── */}
      <section className="relative overflow-hidden pt-[clamp(48px,8vw,96px)] pb-[clamp(40px,6vw,72px)] px-[clamp(16px,4vw,32px)]">
        <div
          className="absolute -top-[180px] left-1/2 -translate-x-1/2 w-[min(900px,120vw)] h-[500px] pointer-events-none
                     bg-[radial-gradient(ellipse_at_center,var(--color-accent-soft),transparent_65%)]"
        />
        <div
          className={`${SHELL} relative grid gap-[clamp(32px,5vw,64px)] items-center
                      grid-cols-[repeat(auto-fit,minmax(min(100%,480px),1fr))]`}
        >
          <div className="flex flex-col gap-[22px] items-start">
            <div className="flex gap-2 flex-wrap">
              <span className="inline-flex items-center gap-[7px] text-xs font-medium text-accent border border-accent-line bg-accent-soft px-3 py-1.5 rounded-full">
                <Icon name="shield" size={13} strokeWidth={2} />
                Par des passionnés, contre les scalpers
              </span>
              <span className="inline-flex items-center gap-[7px] text-xs font-medium text-gold border border-gold-line bg-gold-soft px-3 py-1.5 rounded-full">
                <Icon name="users" size={13} strokeWidth={2} />
                Outil communautaire
              </span>
            </div>

            <h1 className="font-display text-[clamp(36px,5.4vw,62px)] font-extrabold tracking-[-0.03em] leading-[1.06] text-balance">
              Achetez vos scellés au <span className="text-accent">prix boutique</span>, avant les
              scalpers.
            </h1>

            <p className="text-[clamp(15px,1.5vw,18px)] text-muted leading-[1.65] max-w-[520px] text-pretty">
              {BRAND} surveille 100+ boutiques françaises et vous alerte dès qu&apos;un scellé
              Pokémon ou One Piece revient en stock ou baisse de prix — au tarif officiel, pas au
              prix gonflé d&apos;eBay ou Cardmarket.
            </p>

            <div className="flex items-center gap-3.5 flex-wrap pt-1">
              <a
                href="#waitlist"
                className="inline-flex items-center gap-2 bg-accent text-on-accent font-semibold px-6 py-3.5 rounded-xl text-[15px]
                           shadow-[0_8px_28px_-8px_var(--color-accent-line)] hover:brightness-110 transition-[filter]"
              >
                Rejoindre la liste d&apos;attente
                <Icon name="arrowRight" size={16} strokeWidth={2.2} />
              </a>
              <a
                href="#pricing"
                className="inline-flex items-center gap-2 border border-line-strong text-ink font-medium px-[22px] py-3.5 rounded-xl text-[15px]
                           hover:border-dim transition-colors"
              >
                Voir les formules
              </a>
            </div>

            <div className="flex items-center gap-2.5 text-[13px] text-dim flex-wrap">
              <span className="inline-flex items-center gap-1.5">
                <span className="w-[7px] h-[7px] rounded-full bg-ok animate-pulse-dot" />
                Dernier scan il y a 18 min
              </span>
              <span className="text-line-strong">·</span>
              <span>100+ boutiques</span>
              <span className="text-line-strong">·</span>
              <span>5 langues d&apos;édition</span>
            </div>
          </div>

          {/* Collage produits + alertes */}
          <div className="relative w-full max-w-[540px] mx-auto min-h-[clamp(360px,42vw,470px)]">
            <div className="absolute inset-y-[10%] inset-x-[5%] pointer-events-none bg-[radial-gradient(ellipse_at_center,var(--color-gold-soft),transparent_70%)]" />

            <div className="absolute top-[6%] left-[2%] w-[56%] bg-panel border border-line-strong rounded-[18px] p-3.5 -rotate-3 shadow-[0_30px_60px_-20px_rgba(0,0,0,0.6)]">
              <div className="aspect-square flex items-center justify-center bg-panel-2 rounded-xl overflow-hidden">
                <div className="relative w-[88%] h-[88%]">
                  <Image
                    src="/images/products/op17-display.webp"
                    alt="Display One Piece OP-17"
                    fill
                    sizes="(max-width: 768px) 45vw, 300px"
                    className="object-contain"
                    priority
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-2 pt-2.5 px-1 pb-0.5">
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate">Display OP-17</p>
                  <p className="text-[11px] text-dim mt-0.5">One Piece · EN</p>
                </div>
                <span className="font-display text-[15px] font-bold whitespace-nowrap">89,90 €</span>
              </div>
            </div>

            <div className="absolute top-[18%] right-0 w-[46%] bg-panel border border-line-strong rounded-[18px] p-3 rotate-[3.5deg] shadow-[0_30px_60px_-20px_rgba(0,0,0,0.6)] animate-float-y">
              <div className="aspect-[4/5] flex items-center justify-center bg-panel-2 rounded-xl overflow-hidden">
                <div className="relative w-[80%] h-[90%]">
                  <Image
                    src="/images/products/booster-evolutions-prismatiques.png"
                    alt="Booster Évolutions Prismatiques"
                    fill
                    sizes="(max-width: 768px) 38vw, 250px"
                    className="object-contain"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between gap-1.5 pt-2 px-0.5">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold truncate">Évolutions Prismatiques</p>
                  <p className="text-[10px] text-dim mt-0.5">Pokémon · FR</p>
                </div>
              </div>
            </div>

            <div
              className="absolute bottom-[13%] left-[6%] right-[14%] rounded-[14px] px-3.5 py-3 flex items-center gap-3
                         bg-[color-mix(in_srgb,var(--color-panel)_92%,transparent)] backdrop-blur-[8px]
                         border border-ok-line shadow-[0_24px_48px_-16px_rgba(0,0,0,0.65)]"
            >
              <span className="flex items-center justify-center w-9 h-9 rounded-[10px] bg-ok-soft text-ok shrink-0">
                <Icon name="bell" size={18} strokeWidth={2} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-ok">Réappro détectée · il y a 2 min</p>
                <p className="text-xs text-muted mt-[3px] truncate">
                  Display Évolutions Prismatiques —{" "}
                  <span className="text-ink font-semibold">164,90 €</span>
                </p>
              </div>
            </div>

            <div
              className="absolute bottom-0 right-[4%] rounded-[14px] px-3.5 py-2.5 flex items-center gap-2.5
                         bg-[color-mix(in_srgb,var(--color-panel)_92%,transparent)] backdrop-blur-[8px]
                         border border-gold-line shadow-[0_24px_48px_-16px_rgba(0,0,0,0.65)]"
            >
              <span className="text-gold flex">
                <Icon name="trendingDown" size={16} strokeWidth={2} />
              </span>
              <p className="text-xs text-muted">
                Baisse de prix <span className="text-gold font-bold">−18 %</span>
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Chiffres clés ── */}
      <section className="px-[clamp(16px,4vw,32px)] pb-[clamp(48px,7vw,88px)]">
        <div
          className={`${SHELL} border border-line bg-panel rounded-[18px] overflow-hidden
                      grid grid-cols-[repeat(auto-fit,minmax(min(100%,200px),1fr))]`}
        >
          {STATS.map(({ value, label, accent }) => (
            <div
              key={label}
              className="p-[clamp(20px,3vw,30px)] border-r border-b border-line -mr-px -mb-px"
            >
              <p
                className={`font-display text-[clamp(28px,3vw,38px)] font-extrabold tracking-[-0.02em] ${
                  accent ? "text-accent" : ""
                }`}
              >
                {value}
              </p>
              <p className="text-[13px] text-dim mt-1.5">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Manifeste ── */}
      <section id="manifesto" className={SECTION}>
        <div
          className={`${SHELL} grid gap-[clamp(32px,5vw,64px)] items-center
                      grid-cols-[repeat(auto-fit,minmax(min(100%,420px),1fr))]`}
        >
          <div className="flex flex-col gap-[18px]">
            <p className={EYEBROW}>Le manifeste</p>
            <h2 className={H2}>
              Des passionnés.
              <br />
              Pas des scalpers.
            </h2>
            <p className="text-muted leading-[1.7] text-pretty">
              Les éditions limitées partent en quelques minutes — rachetées en masse pour être
              revendues bien plus cher sur eBay ou Cardmarket. {BRAND} remet les passionnés en
              première ligne&nbsp;: on vous prévient dès qu&apos;un produit est disponible en
              boutique, au prix officiel, pour que vous l&apos;achetiez{" "}
              <span className="text-ink font-semibold">avant</span> les revendeurs — pas après, au
              prix fort.
            </p>
            <p className="text-sm text-dim">
              Pas un outil de revente : un outil pour que la communauté paie le juste prix.
            </p>
          </div>

          <div className="bg-panel border border-line rounded-[20px] p-[clamp(20px,3vw,28px)] flex flex-col gap-3.5">
            <div className="flex items-center gap-3.5">
              <div className="w-[74px] h-[74px] rounded-[14px] bg-panel-2 border border-line flex items-center justify-center shrink-0 overflow-hidden">
                <div className="relative w-[86%] h-[86%]">
                  <Image
                    src="/images/products/op16-display.webp"
                    alt="Display One Piece OP-16"
                    fill
                    sizes="74px"
                    className="object-contain"
                  />
                </div>
              </div>
              <div>
                <p className="text-sm font-semibold">Un même display, deux mondes</p>
                <p className="text-xs text-dim mt-[3px]">Exemple relevé sur un display One Piece</p>
              </div>
            </div>

            <div className="flex items-center justify-between gap-2.5 bg-ok-soft border border-ok-line rounded-[14px] px-4 py-3.5">
              <span className="inline-flex items-center gap-2.5 text-sm text-ink">
                <Icon name="shop" size={16} strokeWidth={2} className="text-ok" />
                En boutique, avec {BRAND}
              </span>
              <span className="font-display text-xl font-extrabold text-ok whitespace-nowrap">
                59,90 €
              </span>
            </div>
            <div className="flex items-center justify-between gap-2.5 bg-accent-soft border border-accent-line rounded-[14px] px-4 py-3.5">
              <span className="inline-flex items-center gap-2.5 text-sm text-ink">
                <Icon name="trendingUp" size={16} strokeWidth={2} className="text-accent" />
                Chez un scalper (eBay / Cardmarket)
              </span>
              <span className="font-display text-xl font-extrabold text-accent whitespace-nowrap">
                ≈ 119 €
              </span>
            </div>
            <p className="text-center text-[13px] text-dim">
              Jusqu&apos;à <span className="text-accent font-bold">+100 %</span> de surcote. Soyez là
              au bon moment.
            </p>
          </div>
        </div>
      </section>

      {/* ── Fonctionnalités ── */}
      <section id="features" className={SECTION}>
        <div className={SHELL}>
          <div className="max-w-[640px] mx-auto mb-[clamp(36px,5vw,56px)] text-center flex flex-col gap-3.5">
            <p className={EYEBROW}>Fonctionnalités</p>
            <h2 className={`${H2} text-balance`}>Tout le marché français, surveillé pour vous</h2>
            <p className="text-muted leading-[1.65]">
              {BRAND} suit le stock et les prix des TCG scellés à votre place, pour que vous
              achetiez au tarif officiel sans courir vingt sites.
            </p>
          </div>

          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,300px),1fr))]">
            {FEATURES.map(({ icon, title, desc }) => (
              <div
                key={title}
                className={`${CARD} transition-[border-color,transform] duration-200 hover:border-line-strong hover:-translate-y-0.5`}
              >
                <span className={`${ICON_TILE} bg-accent-soft text-accent`}>
                  <Icon name={icon} />
                </span>
                <h3 className="text-base font-semibold">{title}</h3>
                <p className="text-sm text-muted leading-[1.65]">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comment ça marche ── */}
      <section id="how-it-works" className={SECTION}>
        <div className={SHELL}>
          <div className="max-w-[640px] mx-auto mb-[clamp(36px,5vw,56px)] text-center flex flex-col gap-3.5">
            <p className={EYEBROW}>Comment ça marche</p>
            <h2 className={H2}>Quatre étapes, zéro veille manuelle</h2>
            <p className="text-muted leading-[1.65]">
              De votre liste de surveillance à l&apos;achat au prix officiel.
            </p>
          </div>

          <div className="grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,250px),1fr))]">
            {STEPS.map(({ number, icon, title, desc, ok }) => (
              <div
                key={number}
                className="relative bg-panel border border-line rounded-[18px] px-[22px] py-[26px] overflow-hidden"
              >
                <span
                  aria-hidden="true"
                  className="absolute -top-3.5 right-1.5 font-display text-[88px] font-extrabold text-panel-2 select-none leading-none"
                >
                  {number}
                </span>
                <span
                  className={`relative ${ICON_TILE} mb-4 ${
                    ok ? "bg-ok-soft text-ok" : "bg-accent-soft text-accent"
                  }`}
                >
                  <Icon name={icon} />
                </span>
                <h3 className="relative text-base font-semibold mb-2">{title}</h3>
                <p className="relative text-sm text-muted leading-[1.65]">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Communauté ── */}
      <section id="community" className={SECTION}>
        <div
          className={`${SHELL} relative rounded-[24px] p-[clamp(28px,5vw,56px)] overflow-hidden
                      bg-[linear-gradient(135deg,var(--color-accent-soft),var(--color-gold-soft))] border border-accent-line`}
        >
          <div className="grid gap-[clamp(28px,4vw,48px)] items-center grid-cols-[repeat(auto-fit,minmax(min(100%,400px),1fr))]">
            <div className="flex flex-col gap-[18px] items-start">
              <span className="inline-flex items-center gap-[7px] text-xs font-medium text-accent border border-accent-line bg-accent-soft px-3 py-1.5 rounded-full">
                <Icon name="users" size={13} strokeWidth={2} />
                Une communauté de passionnés
              </span>
              <h2 className={`font-display text-[clamp(26px,3.2vw,38px)] font-extrabold tracking-[-0.025em] leading-[1.12] text-balance`}>
                Vous connaissez une boutique qu&apos;on ne suit pas encore&nbsp;?
              </h2>
              <p className="text-muted leading-[1.7]">
                {BRAND} grandit grâce à sa communauté. Proposez un site avec des produits scellés
                peu ou pas listés chez nous — s&apos;il est compatible avec nos scrapers et
                qu&apos;on l&apos;ajoute, on vous offre{" "}
                <span className="text-gold font-bold">1 mois d&apos;accès</span> en remerciement.
              </p>
              <p className="text-sm text-dim">
                Plus la communauté contribue, plus on couvre le marché — et plus on garde une
                longueur d&apos;avance sur les scalpers.
              </p>
            </div>

            <div className="flex flex-col gap-3">
              {CONTRIBUTION_STEPS.map(({ step, text, gold }) => (
                <div
                  key={step}
                  className="flex items-start gap-3.5 rounded-[14px] px-[18px] py-4 border border-line-strong
                             bg-[color-mix(in_srgb,var(--color-canvas)_75%,transparent)]"
                >
                  <span
                    className={`font-display flex items-center justify-center w-[30px] h-[30px] rounded-full text-[13px] font-bold shrink-0 border ${
                      gold
                        ? "bg-gold-soft border-gold-line text-gold"
                        : "bg-accent-soft border-accent-line text-accent"
                    }`}
                  >
                    {step}
                  </span>
                  <p className="text-sm text-ink leading-[1.6]">
                    {gold ? (
                      <>
                        Si elle est compatible et ajoutée :{" "}
                        <span className="text-gold font-semibold">1 mois offert</span>.
                      </>
                    ) : (
                      text
                    )}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Tarifs ── */}
      <section id="pricing" className={SECTION}>
        <div className={SHELL}>
          <div className="max-w-[700px] mx-auto mb-[clamp(36px,5vw,56px)] text-center flex flex-col gap-3.5">
            <p className={EYEBROW}>Tarifs</p>
            <h2 className={H2}>Des formules simples</h2>
            <p className="text-muted leading-[1.65] text-pretty">
              Deux leviers à parts égales&nbsp;:{" "}
              <span className="text-ink font-semibold">combien d&apos;articles</span> vous suivez,
              et <span className="text-ink font-semibold">à quelle fréquence</span> on scanne le
              marché. Plus c&apos;est fréquent, plus vous êtes prévenu tôt — décisif sur les
              boutiques où tout part en quelques minutes.
            </p>
          </div>

          <div className="grid gap-[18px] items-stretch grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))]">
            {PLANS.map(({ name, nameClass, price, period, items, refresh, perks, highlight }) => (
              <div
                key={name}
                className={
                  "relative rounded-[20px] p-7 flex flex-col " +
                  (highlight
                    ? "bg-[linear-gradient(180deg,var(--color-gold-soft),var(--color-panel)_40%)] border border-gold-line shadow-[0_24px_48px_-20px_var(--color-gold-line)]"
                    : "bg-panel border border-line")
                }
              >
                {highlight && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 text-[11px] font-bold text-on-gold bg-gold px-3.5 py-1 rounded-full whitespace-nowrap">
                    Le plus populaire
                  </span>
                )}
                <h3 className={`font-display text-[17px] font-bold ${nameClass}`}>{name}</h3>
                <div className="mt-3.5 mb-[18px] flex items-end gap-1.5">
                  <span className="font-display text-[34px] font-extrabold tracking-[-0.02em]">
                    {price}
                  </span>
                  {period && <span className="text-sm text-dim mb-1.5">/mois</span>}
                </div>

                <div className="grid grid-cols-2 gap-2 mb-5">
                  <div className="bg-panel-2 border border-line rounded-[10px] px-2 py-[11px] text-center">
                    <p className="text-[10px] text-dim uppercase tracking-[0.06em] mb-[3px]">
                      Articles suivis
                    </p>
                    <p className="text-[13px] font-bold">{items}</p>
                  </div>
                  <div className="bg-panel-2 border border-line rounded-[10px] px-2 py-[11px] text-center">
                    <p className="text-[10px] text-dim uppercase tracking-[0.06em] mb-[3px]">
                      Fréquence
                    </p>
                    <p className="text-[13px] font-bold text-gold">{refresh}</p>
                  </div>
                </div>

                <ul className="flex flex-col gap-[11px] flex-1">
                  {perks.map((perk) => (
                    <li key={perk} className="flex items-start gap-2.5 text-sm text-muted">
                      <Icon
                        name="check"
                        size={15}
                        strokeWidth={2.4}
                        className={`shrink-0 mt-[3px] ${highlight ? "text-gold" : "text-ok"}`}
                      />
                      <span>{perk}</span>
                    </li>
                  ))}
                </ul>

                <a
                  href="#waitlist"
                  className={
                    "mt-[26px] text-center px-5 py-3.5 rounded-xl text-sm " +
                    (highlight
                      ? "font-bold bg-gold text-on-gold hover:brightness-110 transition-[filter]"
                      : "font-semibold bg-panel-2 border border-line-strong text-ink hover:border-dim transition-colors")
                  }
                >
                  Choisir {name}
                </a>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-center bg-panel border border-line rounded-2xl px-6 py-4">
            <span className="text-gold flex">
              <Icon name="users" size={18} strokeWidth={2} />
            </span>
            <p className="text-sm text-muted">
              <span className="font-semibold text-ink">Contribuez, c&apos;est gratuit&nbsp;:</span>{" "}
              proposez une boutique compatible et recevez{" "}
              <span className="text-gold font-semibold">1 mois de Gold offert</span>.
            </p>
          </div>

          <p className="text-center text-xs text-dim mt-5">
            Tarifs indicatifs — la facturation et les abonnements arrivent au lancement.
          </p>
        </div>
      </section>

      {/* ── Personas ── */}
      <section className="py-[clamp(48px,6vw,72px)] px-[clamp(16px,4vw,32px)] border-t border-line">
        <div className={`${SHELL} grid gap-4 grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))]`}>
          {PERSONAS.map(({ icon, title, desc }) => (
            <div key={title} className={`${CARD} gap-3`}>
              <span className={`${ICON_TILE} bg-gold-soft text-gold`}>
                <Icon name={icon} />
              </span>
              <h3 className="text-base font-semibold">{title}</h3>
              <p className="text-sm text-muted leading-[1.65]">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Liste d'attente ── */}
      <section className={SECTION}>
        <div
          id="waitlist"
          className={`${SHELL} scroll-mt-20 relative bg-panel border border-line-strong rounded-[24px] p-[clamp(32px,6vw,64px)] text-center overflow-hidden`}
        >
          <div className="absolute -top-[120px] left-1/2 -translate-x-1/2 w-[600px] h-[300px] pointer-events-none bg-[radial-gradient(ellipse_at_center,var(--color-accent-soft),transparent_70%)]" />
          <div className="relative max-w-[560px] mx-auto flex flex-col gap-5 items-center">
            <h2 className="font-display text-[clamp(26px,3.4vw,40px)] font-extrabold tracking-[-0.025em] leading-[1.12] text-balance">
              Rejoignez la communauté {BRAND}
            </h2>
            <p className="text-muted leading-[1.65]">
              Nous ouvrons bientôt l&apos;accès anticipé — alertes personnalisées, suivi
              d&apos;articles et formules d&apos;abonnement. Laissez votre e-mail et on vous
              prévient.
            </p>
            <form
              action="#"
              className="flex flex-wrap items-center justify-center gap-2.5 w-full max-w-[460px]"
            >
              <label htmlFor="waitlist-email" className="sr-only">
                Adresse e-mail
              </label>
              <input
                id="waitlist-email"
                name="email"
                type="email"
                required
                placeholder="vous@exemple.com"
                className="flex-1 min-w-[220px] bg-canvas border border-line-strong rounded-xl px-4 py-3.5
                           text-sm text-ink placeholder-dim outline-none focus:border-accent transition-colors"
              />
              <button
                type="submit"
                className="bg-accent text-on-accent font-semibold px-[22px] py-3.5 rounded-xl text-sm whitespace-nowrap
                           cursor-pointer hover:brightness-110 transition-[filter]"
              >
                Prévenez-moi
              </button>
            </form>
            <p className="text-xs text-dim">Pas de spam — juste un e-mail à l&apos;ouverture.</p>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-line py-8 px-[clamp(16px,4vw,32px)]">
        <div className={`${SHELL} flex flex-wrap items-center justify-between gap-4`}>
          <div className="flex items-center gap-2.5 text-[13px] text-dim">
            <span className="flex items-center justify-center w-6 h-6 rounded-[7px] bg-accent text-on-accent">
              <Icon name="cards" size={13} strokeWidth={2} />
            </span>
            <span className="font-semibold text-muted">{BRAND}</span>
            <span>— la communauté qui achète au prix boutique</span>
          </div>
          <div className="flex flex-wrap items-center gap-[22px] text-xs">
            {FOOTER_LINKS.map(({ href, label }) => (
              <a key={href} href={href} className="text-dim hover:text-muted transition-colors">
                {label}
              </a>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
