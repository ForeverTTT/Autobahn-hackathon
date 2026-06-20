import FadeIn from "../components/FadeIn";

const AUDIENCE = [
  {
    n: "01",
    name: "Travelers",
    desc: "Find the calmest day and hour to cross the Alps — weeks before you pack the car, not while you're already stuck in it.",
  },
  {
    n: "02",
    name: "Residents",
    desc: "Skip the holiday surges on your own stretch of the A8 or A93, and keep your everyday commute out of the through-traffic.",
  },
  {
    n: "03",
    name: "Logistics",
    desc: "Plan heavy-vehicle runs around predicted peaks, tighten arrival windows, and price routes with reliable travel times.",
  },
  {
    n: "04",
    name: "Tourism",
    desc: "See the arrival waves into Salzburg, Rosenheim and Kufstein before they hit, and staff for the days that actually matter.",
  },
  {
    n: "05",
    name: "Authorities",
    desc: "Spot corridor-wide risk days and the windows where signalling, diversion or roadwork timing pays off most.",
  },
];

export default function ServicesSection() {
  return (
    <section
      id="audience"
      className="bg-[#0C0C0C] rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32"
    >
      <h2
        className="hero-heading font-black uppercase text-center mb-16 sm:mb-20 md:mb-28"
        style={{ fontSize: "clamp(3rem, 12vw, 160px)" }}
      >
        Who It&apos;s For
      </h2>

      <div className="max-w-5xl mx-auto">
        {AUDIENCE.map((s, i) => (
          <FadeIn
            key={s.n}
            delay={i * 0.1}
            className="flex items-center gap-5 sm:gap-8 md:gap-12 py-8 sm:py-10 md:py-12"
            style={{ borderTop: "1px solid rgba(215, 226, 234, 0.18)" }}
          >
            <span
              className="text-[#D7E2EA] font-black leading-none flex-shrink-0"
              style={{ fontSize: "clamp(3rem, 10vw, 140px)" }}
            >
              {s.n}
            </span>
            <div className="flex flex-col gap-2 sm:gap-3">
              <span
                className="text-[#D7E2EA] font-medium uppercase leading-none"
                style={{ fontSize: "clamp(1rem, 2.2vw, 2.1rem)" }}
              >
                {s.name}
              </span>
              <p
                className="text-[#D7E2EA] font-light leading-relaxed max-w-2xl opacity-65"
                style={{ fontSize: "clamp(0.85rem, 1.6vw, 1.25rem)" }}
              >
                {s.desc}
              </p>
            </div>
          </FadeIn>
        ))}
      </div>
    </section>
  );
}
