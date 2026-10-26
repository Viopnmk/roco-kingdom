import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  // 部署路径可由 VITE_BASE 覆盖：GitHub Pages 用子路径 /roco-kingdom/（默认），
  // Cloudflare Pages 等根路径托管用 VITE_BASE=/（构建命令里注入）。
  // 本地 dev 始终根路径。（2026-10-26 部署修复，2026-10-27 增加环境变量覆盖）
  base: process.env.VITE_BASE ?? (mode === "production" ? "/roco-kingdom/" : "/"),
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
