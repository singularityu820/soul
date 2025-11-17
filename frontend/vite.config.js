import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  assetsInclude: ['**/*.gltf', '**/*.bin'],
  server: {
    host: '0.0.0.0',  // 监听所有网络接口
    port: 5173,
    strictPort: true,  // 如果端口被占用则报错而不是换端口
    hmr: {
      host: 'localhost',  // HMR 使用 localhost
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/ws": {
        target: "ws://localhost:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
