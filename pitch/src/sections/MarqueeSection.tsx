import { useEffect, useRef, useState } from "react";

// Product + corridor imagery captured from the live web frontend.
const IMAGES = [
  "/shots/web-map-4.png",
  "/shots/web-calendar.png",
  "/shots/web-map-1.png",
  "/shots/station-map.png",
  "/shots/web-map-3.png",
  "/shots/web-hourly-2.png",
  "/shots/web-map-2.png",
];

const ROW_1 = IMAGES.slice(0, 4);
const ROW_2 = IMAGES.slice(4);

function Tile({ src }: { src: string }) {
  return (
    <img
      src={src}
      loading="lazy"
      alt=""
      className="rounded-2xl object-cover flex-shrink-0 border border-[#D7E2EA]/10"
      style={{ width: 420, height: 270 }}
    />
  );
}

export default function MarqueeSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const onScroll = () => {
      const el = sectionRef.current;
      if (!el) return;
      const sectionTop = el.getBoundingClientRect().top + window.scrollY;
      setOffset((window.scrollY - sectionTop + window.innerHeight) * 0.3);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const x1 = offset - 200;
  const x2 = -(offset - 200);

  return (
    <section
      ref={sectionRef}
      className="bg-[#0C0C0C] pt-24 sm:pt-32 md:pt-40 pb-10 overflow-hidden"
    >
      <div className="flex flex-col gap-3">
        {/* Row 1 — scrolls right */}
        <div
          className="flex gap-3 w-max"
          style={{ transform: `translateX(${x1}px)`, willChange: "transform" }}
        >
          {[...ROW_1, ...ROW_1, ...ROW_1].map((src, i) => (
            <Tile key={`r1-${i}`} src={src} />
          ))}
        </div>

        {/* Row 2 — scrolls left */}
        <div
          className="flex gap-3 w-max"
          style={{ transform: `translateX(${x2}px)`, willChange: "transform" }}
        >
          {[...ROW_2, ...ROW_2, ...ROW_2, ...ROW_2].map((src, i) => (
            <Tile key={`r2-${i}`} src={src} />
          ))}
        </div>
      </div>
    </section>
  );
}
