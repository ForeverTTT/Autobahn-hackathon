import FadeIn from "../components/FadeIn";
import Magnet from "../components/Magnet";
import ContactButton from "../components/ContactButton";
import { DEMO } from "../config";

const NAV_LINKS = [
  { label: "Problem", href: "#problem" },
  { label: "Audience", href: "#audience" },
  { label: "Product", href: "#product" },
  { label: "Demo", href: DEMO.calendar },
];

const TEAM_NAMES = [
  "Hanyan Chen",
  "Kerui Ren",
  "Linhan Li",
  "Xiansheng Huang",
  "Yiru Li",
];

export default function HeroSection() {
  return (
    <section className="relative h-screen flex flex-col" style={{ overflowX: "clip" }}>
      {/* Navbar */}
      <FadeIn
        as="nav"
        delay={0}
        y={-20}
        className="flex justify-between px-6 md:px-10 pt-6 md:pt-8 text-[#D7E2EA] font-medium uppercase tracking-wider text-sm md:text-lg lg:text-[1.4rem]"
      >
        {NAV_LINKS.map((link) => (
          <a
            key={link.label}
            href={link.href}
            {...(link.href.startsWith("http")
              ? { target: "_blank", rel: "noreferrer" }
              : {})}
            className="hover:opacity-70 transition-opacity duration-200"
          >
            {link.label}
          </a>
        ))}
      </FadeIn>

      {/* Hero heading */}
      <div className="overflow-hidden">
        <FadeIn
          as="h1"
          delay={0.15}
          y={40}
          className="hero-heading text-center font-black uppercase tracking-tight leading-none whitespace-nowrap w-full text-[13vw] sm:text-[14vw] md:text-[15vw] lg:text-[16vw] mt-6 sm:mt-4 md:-mt-2"
        >
          AlpineFlow
        </FadeIn>
      </div>

      <FadeIn
        as="p"
        delay={0.25}
        y={20}
        className="mx-auto mt-1 text-center text-[#D7E2EA] font-light tracking-normal leading-snug px-6"
        style={{ fontSize: "clamp(0.85rem, 1.35vw, 1.25rem)" }}
      >
        Long-range, explainable traffic forecasting for the A8 east and A93 south alpine corridors
      </FadeIn>

      {/* Bottom bar */}
      <div className="mt-auto flex justify-between items-end px-6 md:px-10 pb-7 sm:pb-8 md:pb-10">
        <FadeIn delay={0.35} y={20} className="flex flex-col items-start gap-1">
          <div
            className="flex flex-col gap-1 text-white font-light tracking-wide"
            style={{ fontSize: "clamp(0.85rem, 1.25vw, 1.15rem)" }}
          >
            {TEAM_NAMES.map((name) => (
              <span key={name}>{name}</span>
            ))}
          </div>
        </FadeIn>

        <FadeIn delay={0.5} y={20}>
          <ContactButton label="View live demo" href={DEMO.calendar} />
        </FadeIn>
      </div>

      {/* Floating product window — centred, overlapping the heading. */}
      <div className="absolute left-1/2 -translate-x-1/2 z-10 top-1/2 -translate-y-1/2 sm:top-auto sm:translate-y-0 sm:bottom-[4%] md:bottom-[5%] pointer-events-none">
        <FadeIn delay={0.6} y={30}>
          <div className="hero-product-float">
            <video
              src="/shots/maprecord1.mp4"
              autoPlay
              loop
              muted
              playsInline
              className="w-[330px] sm:w-[460px] md:w-[570px] lg:w-[660px] rounded-2xl border border-[#D7E2EA]/25 shadow-[0_30px_80px_rgba(0,0,0,0.6)] select-none"
              draggable={false}
            />
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
