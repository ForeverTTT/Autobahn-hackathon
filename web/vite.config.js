import { defineConfig } from "vite";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => {
  const demoApiPort = process.env.DEMO_API_PORT || "8000";
  const agentSessionId =
    command === "serve"
      ? `dev-${Date.now()}-${Math.random().toString(36).slice(2)}`
      : "production";

  return {
    plugins: [react()],
    define: {
      "import.meta.env.VITE_AGENT_SESSION_ID": JSON.stringify(agentSessionId),
    },
    server: {
      proxy: {
        "/api": `http://127.0.0.1:${demoApiPort}`,
      },
    },
    build: {
      // Multi-page: the main app (index.html) and the standalone pitch deck
      // (pitch.html) build independently. The frontend is untouched.
      rollupOptions: {
        input: {
          main: resolve(__dirname, "index.html"),
          pitch: resolve(__dirname, "pitch.html"),
        },
      },
    },
  };
});
