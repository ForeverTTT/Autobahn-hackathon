import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Standalone pitch deck — its own Vite project, fully separate from web/.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
  },
});
