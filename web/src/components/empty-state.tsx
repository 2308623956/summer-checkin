import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * 空态。文案规则（`docs/tech/frontend.md` §4/§9）：
 * **不画空坐标轴**，不给"暂无数据"这种死胡同，要给出下一步动作。
 */
export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description: string;
  action?: { href: string; label: string };
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border px-6 py-12 text-center",
        className,
      )}
    >
      <p className="text-base font-medium">{title}</p>
      <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
      {action ? (
        <Link
          href={action.href}
          className="mt-4 rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-foreground"
        >
          {action.label}
        </Link>
      ) : null}
    </div>
  );
}
