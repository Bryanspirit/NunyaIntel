// Vite: dev server + production bundler for the React app.
// In development the React app runs on :5273 and forwards /api/* to the Python API on :8765
// (the "proxy"), so the browser only ever talks to one address and needs no CORS setup.
//
// Ports: 5273/8765 rather than the usual 5173/8000, which other local projects (e.g. Docker
// containers) often occupy. If you change the API port (`nunyaintel serve --port`), change it here.
// host 127.0.0.1 is explicit: "localhost" can resolve to IPv6 (::1) and silently reach a
// different server that holds the same port on IPv4.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";


export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5273,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: { outDir: "dist" },
});
