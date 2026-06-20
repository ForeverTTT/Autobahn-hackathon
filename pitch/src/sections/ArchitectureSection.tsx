import FadeIn from "../components/FadeIn";

export default function ArchitectureSection() {
  return (
    <section
      id="architecture"
      className="relative z-10 -mt-10 sm:-mt-12 md:-mt-14 bg-white rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32"
    >
      <FadeIn
        as="h2"
        delay={0}
        y={40}
        className="text-[#0C0C0C] font-black uppercase leading-none tracking-tight text-center mb-10 sm:mb-12 md:mb-16"
        style={{ fontSize: "clamp(3rem, 11vw, 150px)" }}
      >
        Project Architecture
      </FadeIn>

      <FadeIn
        delay={0.1}
        y={50}
        className="mx-auto max-w-3xl overflow-hidden rounded-[28px] sm:rounded-[36px] md:rounded-[44px] border border-[#0C0C0C]/10 bg-white"
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
