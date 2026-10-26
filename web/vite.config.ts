import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  // GitHub Pages 项目站点部署在 /roco-kingdom/ 子路径下，生产构建须带 base；
  // 本地 dev 保持根路径（2026-10-26 部署修复）
  base: mode === "production" ? "/roco-kingdom/" : "/",
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
}));
