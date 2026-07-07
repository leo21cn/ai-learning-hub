import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  optimizeDeps: {
    // PDF.js 体积大、含 .mjs 异步 worker;交由运行时动态加载避免 HMR 卡顿
    exclude: ["pdfjs-dist"],
  },
  worker: {
    format: "es",
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:18765",
        changeOrigin: true,
      },
      "/admin": {
        target: "http://127.0.0.1:18765",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    target: "es2022",
  },
});
