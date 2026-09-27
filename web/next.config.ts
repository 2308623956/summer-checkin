import type { NextConfig } from "next";

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
