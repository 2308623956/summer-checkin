import { headers } from "next/headers";
import { NextResponse } from "next/server";
import { SignJWT, importPKCS8 } from "jose";

import { auth } from "@/lib/auth";

/**
 * 签发 service 用的短期 JWT（`docs/tech/frontend.md` §5）。
 *
 * - **私钥只在 web 侧**，service 只有公钥：签发权不扩散（`design.md` D2）。
 * - 只承载 `sub`（= `user.id`）与 `email`，有效期 15 分钟。
 * - 写进 httpOnly cookie，浏览器拿不到 token 内容，也不需要拿。
 */

export const SERVICE_COOKIE = "summer_service_jwt";
const TOKEN_TTL_SECONDS = 15 * 60;

export async function POST() {
  // 先确认当前会话有效：没有会话就不该签发 token。
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session?.user) {
    return NextResponse.json(
      { error: { code: "AUTH_REQUIRED", message: "请先登录" } },
      { status: 401 },
    );
  }

  const privateKeyPem = process.env.SUMMER_JWT_PRIVATE_KEY?.replace(/\\n/g, "\n");
  if (!privateKeyPem) {
    // 配置缺失是服务端问题，不该让前端看到细节，但服务端要能立刻定位。
    console.error("[service-token] SUMMER_JWT_PRIVATE_KEY is not configured");
    return NextResponse.json(
      { error: { code: "INTERNAL", message: "服务配置缺失" } },
      { status: 500 },
    );
  }

  const key = await importPKCS8(privateKeyPem, "RS256");
  const token = await new SignJWT({ email: session.user.email })
    .setProtectedHeader({ alg: "RS256" })
    .setSubject(session.user.id)
    .setIssuedAt()
    .setExpirationTime(`${TOKEN_TTL_SECONDS}s`)
    .sign(key);

  const response = NextResponse.json({ data: { expiresIn: TOKEN_TTL_SECONDS } });
  response.cookies.set(SERVICE_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: TOKEN_TTL_SECONDS,
  });
  return response;
}

/** 登出时清掉它（`frontend.md` §5：清会话 + 清 service cookie）。 */
export async function DELETE() {
  const response = NextResponse.json({ data: { ok: true } });
  response.cookies.delete(SERVICE_COOKIE);
  return response;
}
