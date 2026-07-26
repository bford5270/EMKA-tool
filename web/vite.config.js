import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies API calls to the local FastAPI service (make serve).
// Everything stays on localhost / the isolated LAN — no external calls.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/query": "http://127.0.0.1:8000",
      "/flag": "http://127.0.0.1:8000",
      "/source": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/corpus": "http://127.0.0.1:8000",
    },
  },
});
