import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import FadeIn from "../components/FadeIn";
import LiveProjectButton from "../components/LiveProjectButton";

interface Project {
  n: string;
  name: string;
  category: string;
  col1a: string;
  col1b: string;
  col2: string;
}

const img = (url: string) =>
  `https://images.higgs.ai/?default=1&output=webp&url=${encodeURIComponent(url)}&w=1280&q=85`;

const CF = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P";

const PROJECTS: Project[] = [
  {
    n: "01",
    name: "Nextlevel Studio",
    category: "Client",
    col1a: img(`${CF}/hf_20260412_055344_5eff02e0-87a5-41ce-b64f-eb08da8f33db.png`),
    col1b: img(`${CF}/hf_20260412_055431_11d841fd-8b41-46a5-82e4-b04f2407a7d8.png`),
    col2: img(`${CF}/hf_20260412_055451_e317bf2d-28d4-48cc-86b0-6f72f25b6327.png`),
  },
  {
    n: "02",
    name: "Aura Brand Identity",
    category: "Personal",
    col1a: img(`${CF}/hf_20260412_055654_911201c5-36d9-4bc6-bac7-331adfce159f.png`),
    col1b: img(`${CF}/hf_20260412_055723_5ceda0b8-d9c2-4665-b2e3-83ba19ba76d1.png`),
    col2: img(`${CF}/hf_20260412_055753_adc5dcbd-a8e6-49c0-b43a-9b030d835cea.png`),
  },
  {
    n: "03",
    name: "Solaris Digital",
    category: "Client",
    col1a: img(`${CF}/hf_20260412_055759_963cfb0b-4bd1-4b0f-9d0a-09bd6cf95b2f.png`),
    col1b: img(`${CF}/hf_20260412_060108_438f781a-9846-4dcc-89ab-c4e6cb830f5b.png`),
    col2: img(`${CF}/hf_20260412_055818_9d062121-ad7e-46b9-999a-1a6a692ef1ee.png`),
  },
];

const RADIUS = "rounded-[40px] sm:rounded-[50px] md:rounded-[60px]";

function ProjectCard({
  project,
  index,
  total,
  progress,
}: {
  project: Project;
  index: number;
  total: number;
  progress: ReturnType<typeof useScroll>["scrollYProgress"];
}) {
  const targetScale = 1 - (total - 1 - index) * 0.03;
  const range: [number, number] = [index / total, 1];
  const scale = useTransform(progress, range, [1, targetScale]);

  return (
    <div className="h-[85vh] sticky top-24 md:top-32 flex justify-center">
      <motion.div
        style={{ scale, top: `${index * 28}px` }}
        className={`relative w-full max-w-6xl ${RADIUS} border-2 border-[#D7E2EA] bg-[#0C0C0C] p-4 sm:p-6 md:p-8 origin-top`}
      >
        {/* Top row */}
        <div className="flex items-center justify-between gap-4 mb-4 sm:mb-6 md:mb-8">
          <div className="flex items-center gap-4 sm:gap-6 md:gap-8 min-w-0">
            <span
              className="text-[#D7E2EA] font-black leading-none flex-shrink-0"
              style={{ fontSize: "clamp(3rem, 10vw, 140px)" }}
            >
              {project.n}
            </span>
            <div className="flex flex-col gap-1 sm:gap-2 min-w-0">
              <span className="text-[#D7E2EA]/60 font-medium uppercase tracking-widest text-xs sm:text-sm">
                {project.category}
              </span>
              <span
                className="text-[#D7E2EA] font-medium uppercase leading-none truncate"
                style={{ fontSize: "clamp(1.1rem, 2.6vw, 2.4rem)" }}
              >
                {project.name}
              </span>
            </div>
          </div>
          <div className="hidden sm:block flex-shrink-0">
            <LiveProjectButton />
          </div>
        </div>

        {/* Bottom row — image grid */}
        <div className="flex gap-3 sm:gap-4">
          <div className="w-[40%] flex flex-col gap-3 sm:gap-4">
            <img
              src={project.col1a}
              alt={project.name}
              loading="lazy"
              className={`w-full object-cover ${RADIUS}`}
              style={{ height: "clamp(130px, 16vw, 230px)" }}
            />
            <img
              src={project.col1b}
              alt={project.name}
              loading="lazy"
              className={`w-full object-cover ${RADIUS}`}
              style={{ height: "clamp(160px, 22vw, 340px)" }}
            />
          </div>
          <div className="w-[60%]">
            <img
              src={project.col2}
              alt={project.name}
              loading="lazy"
              className={`w-full h-full object-cover ${RADIUS}`}
            />
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function ProjectsSection() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end end"],
  });

  return (
    <section className="relative z-10 -mt-10 sm:-mt-12 md:-mt-14 bg-[#0C0C0C] rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32">
      <FadeIn
        as="h2"
        delay={0}
        y={40}
        className="hero-heading font-black uppercase leading-none tracking-tight text-center mb-16 sm:mb-20 md:mb-28"
        style={{ fontSize: "clamp(3rem, 12vw, 160px)" }}
      >
        Project
      </FadeIn>

      <div ref={containerRef}>
        {PROJECTS.map((project, i) => (
          <ProjectCard
            key={project.n}
            project={project}
            index={i}
            total={PROJECTS.length}
            progress={scrollYProgress}
          />
        ))}
      </div>
    </section>
  );
}
