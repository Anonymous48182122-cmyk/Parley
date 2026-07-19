import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "prompt",
      // Check for a new service worker every 60s while the app is open, on
      // top of the browser's own checks on load — so "Update available"
      // shows up promptly instead of only after a fresh app open.
      workbox: { cleanupOutdatedCaches: true },
      includeAssets: ["favicon-64.png"],
      manifest: {
        id: "/",
        name: "Parley",
        short_name: "Parley",
        description: "Parley — nine legendary investor frameworks debate any stock, live",
        start_url: "/",
        scope: "/",
        theme_color: "#080C16",
        background_color: "#080C16",
        display: "standalone",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8420",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
