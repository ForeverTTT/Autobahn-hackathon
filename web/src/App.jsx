import { useEffect, useRef, useState } from "react";
import CalendarPage from "./components/CalendarPage";
// Legacy Leaflet map — kept in the codebase but no longer routed.
// eslint-disable-next-line no-unused-vars
import MapPage from "./components/MapPage";
import HourlyMapPage from "./components/HourlyMapPage";
import MyPlanPage from "./components/MyPlanPage";
import PillNav from "./components/PillNav";
import AgentBot from "../agent/AgentBot";

const pages = ["calendar", "map", "myplan"];

const NAV_ITEMS = [
  { label: "Calendar", href: "#/calendar" },
  { label: "Map", href: "#/map" },
  { label: "My Plan", href: "#/myplan" },
];

function pageFromHash() {
  const page = window.location.hash.replace("#/", "").split("?")[0];
  return pages.includes(page) ? page : "calendar";
}

export default function App() {
  const [page, setPage] = useState(pageFromHash);
  const shellRef = useRef(null);
  const navRef = useRef(null);
  const initialIndex = useRef(Math.max(0, pages.indexOf(pageFromHash())));

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHashChange);

    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/calendar");
    }

    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // Lock the whole UI to a fixed "design width" and scale it uniformly so the
  // proportions never change between screens / browser zoom levels. Above the
  // design width (incl. zooming out, which widens the viewport) we set a `zoom`
  // on <html> = realWidth / DESIGN, making every vw/vh resolve as if the
  // viewport were exactly DESIGN px wide, then magnified — so layout, fonts and
  // spacing all scale together. Below DESIGN we leave zoom at 1 and the existing
  // responsive rules handle narrow windows / phones.
  //
  // `zoom` (not transform: scale) is used on purpose: it keeps position:fixed,
  // the Leaflet map and GSAP ScrollTrigger working, since it scales the real
  // CSS pixel grid rather than just the painted output.
  useEffect(() => {
    const DESIGN_WIDTH = 1500;
    const html = document.documentElement;

    const applyScale = () => {
      // measure in true (un-zoomed) pixels first
      html.style.zoom = "1";
      const navH = navRef.current?.offsetHeight ?? 78;
      shellRef.current?.style.setProperty("--nav-h", `${navH}px`);
      const realWidth = window.innerWidth; // innerWidth is at zoom:1 right now
      const z = realWidth > DESIGN_WIDTH ? realWidth / DESIGN_WIDTH : 1;
      html.style.zoom = String(z);
    };

    applyScale();
    window.addEventListener("resize", applyScale);
    return () => {
      window.removeEventListener("resize", applyScale);
      html.style.zoom = "";
    };
  }, []);

  return (
    <div className="app-shell" ref={shellRef}>
      <header className="topbar" ref={navRef}>
        <div className="topbar-inner">
          {page !== "map" && (
            <a className="app-brand" href="#/calendar" aria-label="AlpineFlow">
              <span>ALPINEFLOW</span>
            </a>
          )}
          <PillNav
            items={NAV_ITEMS}
            activeHref={`#/${page}`}
            baseColor="#000000"
            pillColor="#ffffff"
            pillTextColor="#000000"
            hoveredPillTextColor="#ffffff"
            initialLoadAnimation={false}
          />
        </div>
      </header>

      <main>
        {page === "calendar" && <CalendarPage />}
        {/* "Map" now shows the scroll version (formerly Hourly) */}
        {page === "map" && <HourlyMapPage />}
        {page === "myplan" && <MyPlanPage />}
      </main>
      <AgentBot />
    </div>
  );
}
