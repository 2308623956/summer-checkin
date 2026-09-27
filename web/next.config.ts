import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import path from "node:path";

// 从仓库根加载 .env.local / .env
// Next.js 默认只加载自己目录的 .env*，这里让它读根目录的统一配置
loadEnvConfig(path.resolve(__dirname, ".."));

const nextConfig: NextConfig = {
  reactCompiler: true,
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  // Docker 部署：生成自包含的最小运行时目录
  output: "standalone",
  async rewrites() {
    // 本地开发把 /api/v1/* 转发给 service。
    // 线上不需要这条：nginx 按路径分流（见 infra/nginx/）。
    const serviceUrl = process.env.SUMMER_SERVICE_URL ?? "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${serviceUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
