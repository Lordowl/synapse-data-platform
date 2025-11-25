import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const host = process.env.TAURI_DEV_HOST;

// https://vitejs.dev/config/
export default defineConfig(async () => ({
  plugins: [react()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  clearScreen: false,

  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
        protocol: "ws",
        host,
        port: 1421,
      }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },

  // Configurazione specifica per il build
  build: {
    // Target compatibile con Tauri
    target: process.env.TAURI_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    // Non minificare se siamo in debug
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    // Sourcemap solo in debug
    sourcemap: !!process.env.TAURI_DEBUG,
    // Configurazione rollup per gestire i moduli esterni
    rollupOptions: {
      external: (id) => {
        // Non externalizzare i plugin Tauri durante il build
        return false;
      }
    }
  },

  // Assicurati che i plugin Tauri siano trattati correttamente
  define: {
    global: 'globalThis',
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
}));