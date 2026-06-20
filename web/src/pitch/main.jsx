import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import PitchDeck from "./PitchDeck";
import "./pitch.css";

createRoot(document.getElementById("pitch-root")).render(
  <StrictMode>
    <PitchDeck />
  </StrictMode>,
);
