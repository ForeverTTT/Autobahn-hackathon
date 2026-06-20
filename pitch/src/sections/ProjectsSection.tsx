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
  hideDemo?: boolean;
  layout?:
    | "default"
    | "model-overview"
    | "model-results"
    | "agent-architecture"
    | "ui-showcase";
}

const PROJECTS: Project[] = [
  {
    n: "01",
    name: "CatBoost Decision Trees",
    category: "Model · boosted decision trees",
    href: DEMO.hourly,
    col1a: "/shots/catboost_model_architecture.png",
    col1b: "/shots/feature_group_importance_no_construction.png",
    col2: "/shots/feature_group_importance_no_construction.png",
    hideDemo: true,
    layout: "model-overview",
  },
  {
    n: "01",
    name: "CatBoost Validation",
    category: "Validation · forecast quality",
    href: DEMO.hourly,
    col1a: "/shots/1_best_fit_week.png",
    col1b: "/shots/3_best_fit_day.png",
    col2: "/shots/7_daily_profile_by_tagestyp.png",
    hideDemo: true,
    layout: "model-results",
  },
  {
    n: "02",
    name: "Agentic RAG System",
    category: "AI Agent · retrieval augmented reasoning",
    href: DEMO.calendar,
    col1a: "/shots/alpineflow_agent_architecture.png",
    col1b: "/shots/alpineflow_agent_architecture.png",
    col2: "/shots/alpineflow_agent_architecture.png",
    hideDemo: true,
    layout: "agent-architecture",
  },
  {
    n: "03",
    name: "Interactive User Interface",
    category: "Web · interactive forecast UI",
    href: DEMO.hourly,
    col1a: "/shots/ui3.jpeg",
    col1b: "/shots/UI1.jpeg",
    col2: "/shots/ui2.jpeg",
    layout: "ui-showcase",
  },
];

const RADIUS = "rounded-[40px] sm:rounded-[50px] md:rounded-[60px]";

function ProductImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={`w-full bg-white object-contain ${RADIUS} ${className ?? ""}`}
    />
  );
}

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
    <div className="h-[85vh] sticky top-10 md:top-12 flex justify-center">
      <motion.div
        style={{ scale, top: `${index * 28}px` }}
        className={`relative w-full max-w-7xl ${RADIUS} border-2 border-[#D7E2EA] bg-[#0C0C0C] p-4 sm:p-6 md:p-8 origin-top ${
          project.layout === "ui-showcase" ? "md:min-h-[760px]" : ""
        }`}
      >
        {/* Top row */}
        <div className="flex items-center justify-between gap-3 mb-3 sm:mb-4 md:mb-5">
          <div className="flex items-center gap-3 sm:gap-4 md:gap-5 min-w-0">
            <span
              className="text-[#D7E2EA] font-black leading-none flex-shrink-0"
              style={{ fontSize: "clamp(1.8rem, 4.6vw, 64px)" }}
            >
              {project.n}
            </span>
            <div className="flex flex-col min-w-0">
              <span
                className="text-[#D7E2EA] font-medium uppercase leading-none truncate"
                style={{ fontSize: "clamp(0.9rem, 1.55vw, 1.35rem)" }}
              >
                {project.name}
              </span>
            </div>
          </div>
          {!project.hideDemo && (
            <div className="hidden sm:block flex-shrink-0">
              <LiveProjectButton href={project.href} />
            </div>
          )}
        </div>

        {/* Bottom row — image grid */}
        {project.layout === "model-overview" ? (
          <div className="grid grid-cols-1 md:grid-cols-[50%_50%] gap-3 sm:gap-4">
            <div
              className={`h-[360px] sm:h-[430px] md:h-[560px] overflow-hidden bg-white ${RADIUS}`}
            >
              <img
                src={project.col1a}
                alt="CatBoost model architecture"
                loading="lazy"
                className="h-full w-full object-contain scale-[0.96]"
              />
            </div>
            <ProductImage
              src={project.col1b}
              alt="Feature group importance"
              className="h-[360px] sm:h-[430px] md:h-[560px] p-3 sm:p-4 md:p-5"
            />
          </div>
        ) : project.layout === "model-results" ? (
          <div className="grid grid-cols-1 gap-3 sm:gap-4">
            <ProductImage
              src={project.col1a}
              alt="One-week forecast fit"
              className="h-[180px] sm:h-[215px] md:h-[250px] p-3 sm:p-4"
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
              <ProductImage
                src={project.col1b}
                alt="Best-fit forecast day"
                className="h-[170px] sm:h-[205px] md:h-[240px] p-3 sm:p-4"
              />
              <ProductImage
                src={project.col2}
                alt="Daily traffic profile by day type"
                className="h-[170px] sm:h-[205px] md:h-[240px] p-3 sm:p-4"
              />
            </div>
          </div>
        ) : project.layout === "agent-architecture" ? (
          <div className="grid grid-cols-1 md:grid-cols-[34%_66%] gap-3 sm:gap-4">
            <div
              className={`min-h-[240px] md:h-[540px] ${RADIUS} border border-[#D7E2EA]/20 bg-[#D7E2EA]/5 p-6 sm:p-8 md:p-10 flex flex-col justify-center`}
            >
              <span className="text-[#D7E2EA]/60 font-medium uppercase tracking-widest text-[10px] sm:text-xs">
                Agentic RAG
              </span>
              <h3
                className="mt-4 text-[#D7E2EA] font-medium uppercase leading-none"
                style={{ fontSize: "clamp(1.15rem, 2.1vw, 1.9rem)" }}
              >
                Reason over traffic context
              </h3>
              <p className="mt-5 text-[#D7E2EA]/65 font-light leading-relaxed text-sm sm:text-base md:text-lg">
                Intent parsing, live search, forecast tools, and knowledge retrieval work
                together to generate explainable travel advice.
              </p>
            </div>
            <ProductImage
              src={project.col1a}
              alt="Agentic RAG architecture"
              className="h-[320px] sm:h-[420px] md:h-[540px] p-2 sm:p-3 md:p-4"
            />
          </div>
        ) : project.layout === "ui-showcase" ? (
          <div className="grid grid-cols-1 md:grid-cols-[32%_60%] justify-center gap-3 sm:gap-4 px-2 sm:px-4 md:px-8">
            <div className={`h-[300px] sm:h-[420px] md:h-[600px] bg-white p-2 sm:p-3 ${RADIUS}`}>
              <img
                src={project.col1a}
                alt="Hourly traffic mobile interface"
                loading="lazy"
                className={`h-full w-full object-contain ${RADIUS}`}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:gap-4">
              <div className={`h-[180px] sm:h-[225px] md:h-[290px] bg-white p-2 sm:p-3 ${RADIUS}`}>
                <img
                  src={project.col2}
                  alt="Live corridor map interface"
                  loading="lazy"
                  className={`h-full w-full object-contain ${RADIUS}`}
                />
              </div>
              <div className={`h-[180px] sm:h-[225px] md:h-[290px] bg-white p-2 sm:p-3 ${RADIUS}`}>
                <img
                  src={project.col1b}
                  alt="Traffic calendar interface"
                  loading="lazy"
                  className={`h-full w-full object-contain ${RADIUS}`}
                />
              </div>
            </div>
          </div>
        ) : (
          <div className="flex gap-3 sm:gap-4">
            <div className="w-[40%] flex flex-col gap-3 sm:gap-4">
              <img
                src={project.col1a}
                alt={project.name}
                loading="lazy"
                className={`w-full object-contain bg-white ${RADIUS}`}
                style={{ height: "clamp(130px, 16vw, 230px)" }}
              />
              <img
                src={project.col1b}
                alt={project.name}
                loading="lazy"
                className={`w-full object-contain bg-white ${RADIUS}`}
                style={{ height: "clamp(160px, 22vw, 340px)" }}
              />
            </div>
            <div className="w-[60%]">
              <img
                src={project.col2}
                alt={project.name}
                loading="lazy"
                className={`w-full h-full object-contain bg-white ${RADIUS}`}
              />
            </div>
          </div>
        )}
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
            key={`${project.n}-${i}`}
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
