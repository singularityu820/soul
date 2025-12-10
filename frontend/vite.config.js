import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  assetsInclude: ['**/*.gltf', '**/*.bin'],
  // 如果部署在子路径，需要设置 base，例如 base: '/your-app/'
  // base: '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 确保资源内联阈值，小于 4kb 的资源会被内联为 base64
    assetsInlineLimit: 4096,
    // 生成 source map（生产环境可以关闭以减小体积）
    sourcemap: false,
    // 压缩配置
    minify: 'esbuild',
    // 启用 CSS 代码分割
    cssCodeSplit: true,
    // 启用 rollup 选项
    rollupOptions: {
      output: {
        // 手动分包
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          'three-vendor': ['three'],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',  // 监听所有网络接口
    port: 5173,
    strictPort: true,  // 如果端口被占用则报错而不是换端口
    hmr: {
      host: 'localhost',  // HMR 使用 localhost
    },
    proxy: {
      "/api": {
        target: "https://xbxm.cloud:443",
        changeOrigin: true,
        // 移除rewrite规则，保持/api前缀
      },
      "/volcano-image-emotion": {
        target: "https://xbxm.cloud:443",
        changeOrigin: true,
      },
      "/generated_images": {
        target: "https://xbxm.cloud:443",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://xbxm.cloud:443",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});