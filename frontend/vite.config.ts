import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Im Entwicklungsmodus leitet Vite /api an das lokale Backend weiter
// (uv run edgefinder serve --host 127.0.0.1).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8420" },
  },
});
