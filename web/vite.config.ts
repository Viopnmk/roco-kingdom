import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
  },
  server: {
    watch: {
      // Windows 下原生 fs.watch 遇到锁定文件会 EBUSY，改用轮询
      usePolling: true,
      interval: 800,
    },
  },
});
