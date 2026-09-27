"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/utils";
import { signOut } from "@/lib/service-token";

/**
 * 主导航。**没有聊天室入口，也没有 `/review` 与 `/agent/eval`**
 * （ADR-002 与 `design.md` D11 的范围决定）。
 */
const LINKS = [
  { href: "/dashboard", label: "概览" },
  { href: "/checkin", label: "打卡" },
  { href: "/plans", label: "计划" },
  { href: "/docs", label: "资料" },
  { href: "/statistics", label: "统计" },
  { href: "/agent", label: "巡检" },
  { href: "/profile", label: "我的" },
];

export function NavBar() {
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="border-b border-border bg-card">
      <nav className="mx-auto flex max-w-5xl items-center gap-1 px-4 py-3 text-sm">
        <span className="mr-4 font-semibold">Summer Checkin</span>
        {LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "rounded-md px-3 py-1.5",
              pathname === link.href || pathname.startsWith(`${link.href}/`)
                ? "bg-accent text-accent-foreground"
                : "text-muted hover:bg-background hover:text-foreground",
            )}
          >
            {link.label}
          </Link>
        ))}
        <button
          type="button"
          onClick={logout}
          className="ml-auto rounded-md px-3 py-1.5 text-muted hover:bg-background hover:text-foreground"
        >
          退出登录
        </button>
      </nav>
    </header>
  );
}
