/**
 * service token 的签发/续签与登出。
 *
 * 为什么单独一个模块：页面对 `fetch` 的调用要被收在 `src/lib/` 里
 * （`docs/tech/frontend.md` §6 的取数出口约定），页面只调这里导出的函数。
 */

/** 续签 service JWT。`api.ts` 遇到 401 时也走它。 */
export async function refreshServiceToken(): Promise<void> {
  const response = await fetch("/api/service-token", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`service token refresh failed: ${response.status}`);
  }
}

/** 登出：清 Better Auth 会话 + 清 service cookie。 */
export async function signOut(): Promise<void> {
  await fetch("/api/auth/sign-out", { method: "POST", credentials: "include" });
  await fetch("/api/service-token", { method: "DELETE", credentials: "include" });
}
