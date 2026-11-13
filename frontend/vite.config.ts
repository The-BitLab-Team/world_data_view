import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const API_TARGET = process.env.VITE_DEV_API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Em desenvolvimento, a API é acessada pelo mesmo host (sem CORS).
    proxy: {
      "/api": API_TARGET,
      "/docs": API_TARGET,
      "/openapi.json": API_TARGET,
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
