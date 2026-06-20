/**
 * AlpineFlow pitch deck — standalone page, isolated from the main app.
 *
 * This is a PLACEHOLDER scaffold. Drop the real template into the `slides`
 * array (or replace this component wholesale) and the content from
 * doc/SOLUTION.md / doc/material will fill in.
 *
 * It already demonstrates the two goals:
 *  1. Fully separate entry (pitch.html) — does not touch the frontend.
 *  2. Connects to the frontend — the "Live demo" buttons jump to the real app.
 */
import { useEffect, useState } from "react";

// The live frontend lives at the site root with hash routing.
const DEMO = {
  calendar: "/#/calendar",
  map: "/#/map",
  hourly: "/#/hourly",
};

const slides = [
  {
    kind: "title",
    title: "AlpineFlow",
    subtitle:
      "Long-range, explainable traffic forecasting for the A8 East & A93 South holiday corridors",
  },
  {
    kind: "content",
    title: "The problem",
    bullets: [
      "Holiday traffic on the Alpine corridors is brutal but predictable — yet travelers, residents and logistics plan blind.",
      "Existing tools are real-time only. Nobody tells you the best day to leave three weeks out.",
    ],
  },
  {
    kind: "content",
    title: "What we built",
    bullets: [
      "CatBoost hourly forecast for 2026–2029, 12 sites — P10/P50/P90 flow, heavy-vehicle share, speed.",
      "Local GraphRAG + multi-agent FastAPI that explains WHY a day is congested.",
      "Interactive web demo: traffic calendar, segment map, 24h hourly view.",
    ],
    demo: "calendar",
  },
  {
    kind: "content",
    title: "Five users, one corridor",
    bullets: [
      "Traveler — best departure day & time.",
      "Resident — avoid local peaks.",
      "Logistics — reliable arrival windows.",
      "Tourism — prep for arrival surges.",
      "Authority — corridor risk & intervention windows.",
    ],
  },
  {
    kind: "content",
    title: "Pipeline",
    bullets: ["Data → Model (CatBoost) → Agent (GraphRAG) → Frontend"],
    demo: "map",
  },
  {
    kind: "title",
    title: "See it live",
    subtitle: "AlpineFlow — from a 4-year forecast to a single departure decision",
    demo: "calendar",
  },
];

export default function PitchDeck() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "ArrowRight" || e.key === " ") setI((n) => Math.min(n + 1, slides.length - 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const s = slides[i];

  return (
    <div className="deck">
      <div className={`slide slide--${s.kind}`} key={i}>
        {s.kind === "title" ? (
          <>
            <h1 className="slide-title">{s.title}</h1>
            <p className="slide-subtitle">{s.subtitle}</p>
          </>
        ) : (
          <>
            <h2 className="slide-heading">{s.title}</h2>
            <ul className="slide-bullets">
              {s.bullets.map((b, k) => (
                <li key={k}>{b}</li>
              ))}
            </ul>
          </>
        )}

        {s.demo && (
          <a className="demo-link" href={DEMO[s.demo]} target="_blank" rel="noreferrer">
            ▶ Open live demo
          </a>
        )}
      </div>

      <footer className="deck-bar">
        <button onClick={() => setI((n) => Math.max(n - 1, 0))} disabled={i === 0}>
          ←
        </button>
        <span className="deck-count">
          {i + 1} / {slides.length}
        </span>
        <button
          onClick={() => setI((n) => Math.min(n + 1, slides.length - 1))}
          disabled={i === slides.length - 1}
        >
          →
        </button>
      </footer>
    </div>
  );
}
