import { NextRequest, NextResponse } from "next/server";

/**
 * 受保护路由守卫（`docs/tech/frontend.md` §5）：
 * `(dashboard)/**` 与 `/agent/**` 需要会话 cookie，缺失就跳登录并记住来路。
 *
 * 注意这里**只校验 cookie 存在**。真正的鉴权在 service 侧验签——
 * 前端守卫是为了体验（别让用户填完表单才发现要登录），不是安全边界。
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 静态资源绝不能进重定向：把一个 mp4 请求重定向成 HTML，浏览器会报"无法播放"。
  if (/\.[a-z0-9]+$/i.test(pathname)) {
    return NextResponse.next();
  }

  const publicPaths = ["/", "/login", "/register"];
  const isPublic = publicPaths.includes(pathname) || pathname.startsWith("/api/auth/");

  if (isPublic) {
    return NextResponse.next();
  }

  const sessionCookie =
    request.cookies.get("better-auth.session_token")?.value ??
    request.cookies.get("__Secure-better-auth.session_token")?.value ??
    request.cookies.get("session_token")?.value;

  if (!sessionCookie) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("returnTo", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // 排除静态资源、图片与 API（API 自己处理鉴权，交给 service 返回统一错误码）。
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\..*|api/).*)",
  ],
};
