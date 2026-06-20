import { defineConfig } from "vite";
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
  };
});
