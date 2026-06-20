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

      {/* Bottom bar */}
      <div className="mt-auto flex justify-between items-end px-6 md:px-10 pb-7 sm:pb-8 md:pb-10">
        <FadeIn
          as="p"
          delay={0.35}
          y={20}
          className="text-[#D7E2EA] font-light uppercase tracking-wide leading-snug max-w-[170px] sm:max-w-[240px] md:max-w-[300px]"
          style={{ fontSize: "clamp(0.75rem, 1.4vw, 1.5rem)" }}
        >
          long-range, explainable traffic forecasting for the a8 east &amp; a93
          south alpine corridors
        </FadeIn>

        <FadeIn delay={0.5} y={20}>
          <ContactButton label="View live demo" href={DEMO.calendar} />
        </FadeIn>
      </div>

      {/* Floating product window — magnetic, centred, overlapping the heading.
          Centring transforms live on a plain wrapper so they don't fight
          Framer Motion's animation transform on the FadeIn element. */}
      <div className="absolute left-1/2 -translate-x-1/2 z-10 top-1/2 -translate-y-1/2 sm:top-auto sm:translate-y-0 sm:bottom-[6%] md:bottom-[8%] pointer-events-none">
        <FadeIn delay={0.6} y={30}>
          <Magnet
            padding={150}
            strength={4}
            activeTransition="transform 0.3s ease-out"
            inactiveTransition="transform 0.6s ease-in-out"
          >
            <img
              src="/shots/web-map-4.png"
              alt="AlpineFlow segment map and forecast"
              className="w-[300px] sm:w-[420px] md:w-[520px] lg:w-[600px] rounded-2xl border border-[#D7E2EA]/25 shadow-[0_30px_80px_rgba(0,0,0,0.6)] select-none"
              draggable={false}
            />
          </Magnet>
        </FadeIn>
      </div>
    </section>
  );
}
