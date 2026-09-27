"use client";

/**
 * `useApi`：极简取数 hook。返回 `{ data, error, loading, refresh }`。
 *
 * **不引 swr / react-query**（`docs/tech/frontend.md` §6）：本项目页面数量有限、
 * 取数模式统一，多一个依赖只会多一层概念。
 */

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

export type UseApiResult<T> = {
  data: T | null;
  error: unknown;
  loading: boolean;
  refresh: () => void;
};

export function useApi<T>(path: string | null, deps: unknown[] = []): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  // 记录"已完成的请求次数"，用它推导 loading：比在 effect 里同步 setState 少一轮渲染。
  const [settled, setSettled] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [requestKey, setRequestKey] = useState(`${path ?? ""}|${nonce}`);

  // 请求标识变化时立刻回到加载态（渲染期比较，不用 effect）。
  const currentKey = `${path ?? ""}|${nonce}`;
  if (currentKey !== requestKey) {
    setRequestKey(currentKey);
    setData(null);
    setError(null);
    setSettled(0);
  }

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;

    apiFetch<T>(path)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(cause);
      })
      .finally(() => {
        if (!cancelled) setSettled((value) => value + 1);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, nonce, ...deps]);

  const refresh = useCallback(() => setNonce((value) => value + 1), []);

  // 还没拿到结果就是加载中；path 为 null 表示"这次不取数"。
  const loading = path !== null && settled === 0;

  return { data, error, loading, refresh };
}
