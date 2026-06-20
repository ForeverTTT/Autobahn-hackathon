import FadeIn from "../components/FadeIn";

export default function ArchitectureSection() {
  return (
    <section
      id="architecture"
      className="relative z-10 -mt-10 sm:-mt-12 md:-mt-14 bg-[#0C0C0C] rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32"
    >
      <FadeIn
        as="h2"
        delay={0}
        y={40}
        className="hero-heading font-black uppercase leading-none tracking-tight text-center mb-10 sm:mb-12 md:mb-16"
        style={{ fontSize: "clamp(3rem, 11vw, 150px)" }}
      >
        Project Architecture
      </FadeIn>

      <FadeIn
        delay={0.1}
        y={50}
        className="mx-auto max-w-5xl overflow-hidden rounded-[32px] sm:rounded-[44px] md:rounded-[56px] border border-[#D7E2EA]/20 bg-[#111]"
      >
        <img
          src="/shots/project_architecture.png"
          alt="Project architecture diagram"
          loading="lazy"
          className="block w-full"
        />
      </FadeIn>
    </section>
  );
}
