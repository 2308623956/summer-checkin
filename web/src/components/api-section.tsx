"use client";

import { ErrorState } from "@/components/error-state";
import { useApi } from "@/lib/use-api";

/**
 * 统一取数渲染器：把"初始 / 加载 / 成功 / 失败 / 空"五态收在一处。
 *
 * 每个页面自己写这五态的话，总有一两个页面漏掉失败态，线上就是白屏
 * （`docs/tech/frontend.md` §3 逐页写明五态，这里提供统一实现）。
 */
export function ApiSection<T>({
  path,
  isEmpty,
  empty,
  children,
  loadingRows = 3,
}: {
  path: string | null;
  /** 判断"取到了但没有内容"。默认认为空数组是空。 */
  isEmpty?: (data: T) => boolean;
  empty: React.ReactNode;
  children: (data: T) => React.ReactNode;
  loadingRows?: number;
}) {
  const { data, error, loading, refresh } = useApi<T>(path);

  if (loading) {
    return (
      <div className="space-y-3" role="status" aria-label="加载中">
        {Array.from({ length: loadingRows }).map((_, index) => (
          <div key={index} className="h-16 animate-pulse rounded-lg bg-border/60" />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState error={error} onRetry={refresh} />;
  }

  if (data === null) {
    return <>{empty}</>;
  }

  if (isEmpty?.(data)) {
    return <>{empty}</>;
  }

  return <>{children(data)}</>;
}
