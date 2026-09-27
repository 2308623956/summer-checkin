"use client";

import { createAuthClient } from "better-auth/react";

/** 浏览器侧的 Better Auth 客户端。只用于登录/注册/登出，不承载业务数据。 */
export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_BETTER_AUTH_URL ?? undefined,
});
