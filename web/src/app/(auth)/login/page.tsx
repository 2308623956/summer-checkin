"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { authClient } from "@/lib/auth-client";
import { refreshServiceToken } from "@/lib/service-token";

/** 登录成功后**立刻**换 service token：否则第一个业务请求会先吃一个 401。 */
function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const redirectTo = params.get("returnTo") ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const { error: signInError } = await authClient.signIn.email({ email, password });
    if (signInError) {
      // 登录失败只说"邮箱或密码不对"，不区分"用户不存在"与"密码错误"——
      // 区分开等于给了一个枚举用户名的接口。
      setError("邮箱或密码不正确");
      setSubmitting(false);
      return;
    }

    await refreshServiceToken();
    router.push(redirectTo);
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="text-2xl font-semibold">登录</h1>
      <p className="mt-2 text-sm text-muted">用邮箱和密码进入你的打卡空间。</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block">
          <span className="text-sm font-medium">邮箱</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-sm font-medium">密码</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
          />
        </label>

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-60"
        >
          {submitting ? "登录中…" : "登录"}
        </button>
      </form>

      <p className="mt-6 text-sm text-muted">
        还没有账号？{" "}
        <a href="/register" className="text-accent underline">
          去注册
        </a>
      </p>
    </main>
  );
}

/**
 * `useSearchParams` 必须包在 Suspense 里，否则整页会在构建时被判成需要 CSR bailout
 * 而预渲染失败（Next 16 直接让 `next build` 报错退出）。
 */
export default function LoginPage() {
  return (
    <Suspense fallback={<main className="mx-auto max-w-sm px-4 py-24 text-sm text-muted">加载中…</main>}>
      <LoginForm />
    </Suspense>
  );
}
