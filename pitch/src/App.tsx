import HeroSection from "./sections/HeroSection";
import MarqueeSection from "./sections/MarqueeSection";
import AboutSection from "./sections/AboutSection";
import ServicesSection from "./sections/ServicesSection";
import ArchitectureSection from "./sections/ArchitectureSection";
import ProjectsSection from "./sections/ProjectsSection";

export default function App() {
  return (
    <main className="bg-[#0C0C0C] font-kanit" style={{ overflowX: "clip" }}>
      <HeroSection />
      <MarqueeSection />
      <AboutSection />
      <ServicesSection />
      <ArchitectureSection />
      <ProjectsSection />
    </main>
  );
}
