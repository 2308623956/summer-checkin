import { EmptyState } from "@/components/empty-state";
import { actionFor, messageFor } from "@/lib/error-messages";

/**
 * 失败态。三种失败给三种出路（`docs/tech/frontend.md` §7）：
 * 认证过期 → 去登录；上游抖动 → 可点重试；其余 → 说明 + 重试。
 *
 * `requestId` 只在 INTERNAL 时显示，且可复制——用户报错时贴一个 id 就能定位链路。
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const action = actionFor(error);
  const message = messageFor(error);
  const requestId = extractRequestId(error);

  if (action === "relogin") {
    return (
      <EmptyState
        title={message}
        description="登录状态已过期。重新登录后你之前看到的内容还在。"
        action={{ href: "/login", label: "去登录" }}
      />
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card px-6 py-8 text-center">
      <p className="text-base font-medium">{message}</p>
      {action === "retry" ? (
        <p className="mt-2 text-sm text-muted">上游服务暂时不可用，稍后重试通常就好了。</p>
      ) : null}
      {requestId ? (
        <p className="mt-2 text-xs text-muted">
          排查编号：<code className="select-all">{requestId}</code>
        </p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-background"
        >
          重试
        </button>
      ) : null}
    </div>
  );
}

function extractRequestId(error: unknown): string | undefined {
  if (typeof error === "object" && error !== null && "requestId" in error) {
    const value = (error as { requestId?: unknown }).requestId;
    return typeof value === "string" && value ? value : undefined;
  }
  return undefined;
}
