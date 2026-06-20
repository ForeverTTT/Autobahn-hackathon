// The live frontend (web/) — the pitch's "Live Demo" links jump here.
// run_demo.py injects VITE_FRONTEND_BASE so the links always match the port the
// demo script launched the web app on. Falls back to the web dev default.
export const FRONTEND_BASE =
  import.meta.env.VITE_FRONTEND_BASE || "http://localhost:5173";

export const DEMO = {
  calendar: `${FRONTEND_BASE}/#/calendar`,
  map: `${FRONTEND_BASE}/#/map`,
  hourly: `${FRONTEND_BASE}/#/hourly`,
};
