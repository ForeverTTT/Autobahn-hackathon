import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import FadeIn from "../components/FadeIn";
import LiveProjectButton from "../components/LiveProjectButton";
import { DEMO } from "../config";

interface Project {
  n: string;
  name: string;
  category: string;
  href: string;
  col1a: string;
  col1b: string;
  col2: string;
}

const PROJECTS: Project[] = [
  {
    n: "01",
    name: "Traffic Calendar",
    category: "Web · A8 & A93 · both directions",
    href: DEMO.calendar,
    col1a: "/shots/web-calendar.png",
    col1b: "/shots/web-hourly-2.png",
    col2: "/shots/station-map.png",
  },
  {
    n: "02",
    name: "Segment Map",
    category: "Web · Leaflet · scroll-driven",
    href: DEMO.map,
    col1a: "/shots/web-map-1.png",
    col1b: "/shots/web-map-2.png",
    col2: "/shots/web-map-4.png",
  },
  {
    n: "03",
    name: "Hourly Forecast",
    category: "CatBoost v4 · P10 / P50 / P90",
    href: DEMO.hourly,
    col1a: "/shots/web-map-3.png",
    col1b: "/shots/web-calendar.png",
    col2: "/shots/web-map-4.png",
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
            <LiveProjectButton href={project.href} />
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
    <section
      id="product"
      className="relative z-10 -mt-10 sm:-mt-12 md:-mt-14 bg-[#0C0C0C] rounded-t-[40px] sm:rounded-t-[50px] md:rounded-t-[60px] px-5 sm:px-8 md:px-10 py-20 sm:py-24 md:py-32"
    >
      <FadeIn
        as="h2"
        delay={0}
        y={40}
        className="hero-heading font-black uppercase leading-none tracking-tight text-center mb-16 sm:mb-20 md:mb-28"
        style={{ fontSize: "clamp(3rem, 12vw, 160px)" }}
      >
        The Product
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
