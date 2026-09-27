import Link from "next/link";

/** 落地页：未登录也能看，说明这个 App 做什么。 */
export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-4">
      <h1 className="text-3xl font-semibold">Summer Checkin</h1>
      <p className="mt-4 text-muted">
        每天记一笔学习进展，系统帮你看着节奏：连续天数、任务完成度、该补的弱项。
      </p>

      <div className="mt-8 flex gap-3">
        <Link
          href="/login"
          className="rounded-md bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground"
        >
          登录
        </Link>
        <Link
          href="/register"
          className="rounded-md border border-border px-5 py-2.5 text-sm font-medium"
        >
          注册
        </Link>
      </div>

      <p className="mt-8 text-xs text-muted">当前是骨架版本，打卡与巡检的写入还没开通。</p>
    </main>
  );
}
