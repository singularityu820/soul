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
        target: "http://81.68.219.218:5173",
        changeOrigin: true,
        // 移除rewrite规则，保持/api前缀
      },
      "/volcano-image-emotion": {
        target: "http://81.68.219.218:5173",
        changeOrigin: true,
      },
      "/generated_images": {
        target: "http://81.68.219.218:5173",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://81.68.219.218:5173",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});