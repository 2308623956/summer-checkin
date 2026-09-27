"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { authClient } from "@/lib/auth-client";
import { refreshServiceToken } from "@/lib/service-token";

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const { error: signUpError } = await authClient.signUp.email({ name, email, password });
    if (signUpError) {
      // 已有账号是注册流程里唯一值得区分的失败：它给出了明确的下一步（去登录）。
      setError(signUpError.message?.includes("exist") ? "这个邮箱已经注册过了，直接登录吧" : "注册失败，请稍后再试");
      setSubmitting(false);
      return;
    }

    await refreshServiceToken();
    router.push("/dashboard");
    router.refresh();
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <h1 className="text-2xl font-semibold">注册</h1>
      <p className="mt-2 text-sm text-muted">注册后从打卡开始，其余的慢慢来。</p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        <label className="block">
          <span className="text-sm font-medium">昵称</span>
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
          />
        </label>

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
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1 w-full rounded-md border border-border bg-card px-3 py-2 text-sm"
          />
          <span className="mt-1 block text-xs text-muted">至少 8 位</span>
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
          {submitting ? "注册中…" : "注册"}
        </button>
      </form>

      <p className="mt-6 text-sm text-muted">
        已经有账号？{" "}
        <a href="/login" className="text-accent underline">
          去登录
        </a>
      </p>
    </main>
  );
}
