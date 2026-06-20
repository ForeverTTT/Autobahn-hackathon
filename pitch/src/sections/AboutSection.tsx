import FadeIn from "../components/FadeIn";
import AnimatedText from "../components/AnimatedText";
import ContactButton from "../components/ContactButton";
import { DEMO } from "../config";

const DECOR_BASE =
  "https://shrug-person-78902957.figma.site/_components/v2/ebb2b8f25d8e24d5f0a5ca8af4c950de81aa2fd7";

const PROBLEM_TEXT =
  "Every summer the A8 and A93 become the gateway to the Alps — and kilometres of stop-and-go. The jams are punishing, but they are not random: holidays, weather and roadworks make them predictable weeks ahead. AlpineFlow turns that signal into a forecast you can plan around.";

const STATS = [
  { value: "420K+", label: "hourly forecasts" },
  { value: "12", label: "corridor sites" },
  { value: "88%", label: "peak-hour recall" },
  { value: "7", label: "explainable factors" },
];

export default function AboutSection() {
  return (
    <section
      id="problem"
      className="relative min-h-screen flex flex-col items-center justify-center bg-white rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 overflow-hidden"
    >
      {/* Decorative 3D corner objects */}
      <FadeIn
        delay={0.1}
        x={-80}
        y={0}
        duration={0.9}
        className="absolute top-[4%] left-[1%] sm:left-[2%] md:left-[4%] w-[120px] sm:w-[160px] md:w-[210px]"
      >
        <img src={`${DECOR_BASE}/moon_icon.11395d36.png`} alt="" className="w-full" />
      </FadeIn>

      <FadeIn
        delay={0.15}
        x={80}
        y={0}
        duration={0.9}
        className="absolute top-[4%] right-[1%] sm:right-[2%] md:right-[4%] w-[120px] sm:w-[160px] md:w-[210px]"
      >
        <img src={`${DECOR_BASE}/lego_icon-1.703bb594.png`} alt="" className="w-full" />
      </FadeIn>

      <FadeIn
        delay={0.25}
        x={-80}
        y={0}
        duration={0.9}
        className="absolute bottom-[8%] left-[3%] sm:left-[6%] md:left-[10%] w-[100px] sm:w-[140px] md:w-[180px]"
      >
        <img src={`${DECOR_BASE}/p59_1.4659672e.png`} alt="" className="w-full" />
      </FadeIn>

      <FadeIn
        delay={0.3}
        x={80}
        y={0}
        duration={0.9}
        className="absolute bottom-[8%] right-[3%] sm:right-[6%] md:right-[10%] w-[130px] sm:w-[170px] md:w-[220px]"
      >
        <img src={`${DECOR_BASE}/Group_134-1.2e04f3ce.png`} alt="" className="w-full" />
      </FadeIn>

      {/* Heading + animated text + stats + button */}
      <div className="relative z-10 flex flex-col items-center">
        <FadeIn
          as="h2"
          delay={0}
          y={40}
          className="text-[#0C0C0C] font-black uppercase leading-none tracking-tight text-center"
          style={{ fontSize: "clamp(3rem, 12vw, 160px)" }}
        >
          The Problem
        </FadeIn>

        <AnimatedText
          text={PROBLEM_TEXT}
          className="mt-10 sm:mt-14 md:mt-16 text-[#0C0C0C]/70 font-medium text-center leading-relaxed max-w-[620px]"
          style={{ fontSize: "clamp(1rem, 2vw, 1.35rem)" }}
        />

        {/* Model-credibility stats */}
        <FadeIn
          delay={0.1}
          className="mt-12 sm:mt-14 md:mt-16 flex flex-wrap justify-center gap-x-10 gap-y-6 sm:gap-x-16"
        >
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col items-center">
              <span
                className="text-[#0C0C0C] font-black leading-none"
                style={{ fontSize: "clamp(2rem, 5vw, 3.5rem)" }}
              >
                {s.value}
              </span>
              <span className="mt-2 text-[#0C0C0C]/50 font-medium uppercase tracking-widest text-[10px] sm:text-xs">
                {s.label}
              </span>
            </div>
          ))}
        </FadeIn>

        <div className="mt-14 sm:mt-16 md:mt-20">
          <ContactButton label="Explore the forecast" href={DEMO.calendar} />
        </div>
      </div>
    </section>
  );
}
