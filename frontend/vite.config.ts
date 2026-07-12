import { resolve } from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "./",   // relative asset paths so the build loads from file:// (Electron)
  server: { port: 5173, strictPort: true },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        quick: resolve(__dirname, "quick.html"),
      },
    },
  },
});
