import { toNextJsHandler } from "better-auth/next-js";

import { auth } from "@/lib/auth";

/**
 * Better Auth 的**唯一**保留路由（`docs/tech/frontend.md` §3）。
 * 这里不写任何业务接口——业务数据一律经 `/api/v1/*` 走 service。
 */
export const { GET, POST } = toNextJsHandler(auth);
