import { useEffect, useRef, useState } from "react";
import CalendarPage from "./components/CalendarPage";
import MapPage from "./components/MapPage";
import HourlyMapPage from "./components/HourlyMapPage";
import PillNav from "./components/PillNav";
import AgentBot from "../agent/AgentBot";

const pages = ["calendar", "map", "hourly"];

const NAV_ITEMS = [
  { label: "Calendar", href: "#/calendar" },
  { label: "Map", href: "#/map" },
  { label: "Hourly", href: "#/hourly" },
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

  // The nav is fixed to the top; expose its real height so content below it
  // (and the map page's pinned layout) can offset by exactly the right amount.
  useEffect(() => {
    const setNavHeight = () => {
      const h = navRef.current?.offsetHeight ?? 78;
      shellRef.current?.style.setProperty("--nav-h", `${h}px`);
    };
    setNavHeight();
    window.addEventListener("resize", setNavHeight);
    return () => window.removeEventListener("resize", setNavHeight);
  }, []);

  return (
    <div className="app-shell" ref={shellRef}>
      <header className="topbar" ref={navRef}>
        <PillNav
          items={NAV_ITEMS}
          activeHref={`#/${page}`}
          baseColor="#000000"
          pillColor="#ffffff"
          pillTextColor="#000000"
          hoveredPillTextColor="#ffffff"
          initialLoadAnimation={false}
        />
      </header>

      <main>
        {page === "calendar" && <CalendarPage />}
        {page === "map" && <MapPage />}
        {page === "hourly" && <HourlyMapPage />}
      </main>
      <AgentBot />
    </div>
  );
}
