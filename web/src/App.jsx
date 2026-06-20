import { useEffect, useState } from "react";
import CalendarPage from "./components/CalendarPage";
import MapPage from "./components/MapPage";

const pages = new Set(["calendar", "map"]);

function pageFromHash() {
  const page = window.location.hash.replace("#/", "").split("?")[0];
  return pages.has(page) ? page : "calendar";
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 3v3M17 3v3M4.5 9h15M6 5h12a2 2 0 0 1 2 2v12H4V7a2 2 0 0 1 2-2Z" />
    </svg>
  );
}

function MapIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m9 18-5 2V6l5-2 6 2 5-2v14l-5 2-6-2Z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  );
}

export default function App() {
  const [page, setPage] = useState(pageFromHash);

  useEffect(() => {
    const onHashChange = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHashChange);

    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/calendar");
    }

    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = (nextPage) => {
    window.location.hash = `#/${nextPage}`;
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#/calendar" aria-label="AlpineFlow home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
          </span>
          <span>
            <strong>AlpineFlow</strong>
            <small>Autobahn intelligence</small>
          </span>
        </a>

        <nav className="page-tabs" aria-label="Primary navigation">
          <button
            className={page === "calendar" ? "active" : ""}
            type="button"
            onClick={() => navigate("calendar")}
            aria-current={page === "calendar" ? "page" : undefined}
          >
            <CalendarIcon />
            Calendar
          </button>
          <button
            className={page === "map" ? "active" : ""}
            type="button"
            onClick={() => navigate("map")}
            aria-current={page === "map" ? "page" : undefined}
          >
            <MapIcon />
            Map
          </button>
        </nav>

        <div className="live-chip">
          <span />
          Demo forecast
        </div>
      </header>

      <main>{page === "calendar" ? <CalendarPage /> : <MapPage />}</main>
    </div>
  );
}
