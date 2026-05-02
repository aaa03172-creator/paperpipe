import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "tailwindcss";
import autoprefixer from "autoprefixer";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target =
    env.LATTICE_UI_BACKEND_URL?.trim()
    || env.PAPERPIPE_UI_BACKEND_URL?.trim()
    || env.VITE_API_BASE_URL?.trim()
    || "http://localhost:8000";

  return {
    plugins: [react()],
    css: {
      postcss: {
        plugins: [tailwindcss(), autoprefixer()],
      },
    },
    build: {
      rollupOptions: {
        onwarn(warning, defaultHandler) {
          if (
            warning.code === "EVAL"
            && typeof warning.id === "string"
            && warning.id.includes("pdfjs-dist/build/pdf.js")
          ) {
            return;
          }
          defaultHandler(warning);
        },
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
