import { defineConfig, loadEnv } from "vite";
import uni from "@dcloudio/vite-plugin-uni";

// H5 开发时把 /api 代理到后端，前端代码里不出现后端域名
export default defineConfig(({ mode }) => ({
  plugins: [uni()],
  server: {
    warmup: {
      clientFiles: ["./src/pages/*/index.vue"],
    },
    proxy: {
      "/api": {
        target: loadEnv(mode, process.cwd(), '').API_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
}));
