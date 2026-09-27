import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    // `.next*/**` 而不是只忽略 `.next/**`：next.config.ts 支持用 NEXT_DIST_DIR
    // 切换输出目录，只写 `.next` 会让其它构建目录里的编译产物也被 lint。
    ".next*/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);
