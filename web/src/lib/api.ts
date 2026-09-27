/**
 * 取数唯一出口。页面与组件**不得自己拼 fetch**（`docs/tech/frontend.md` §6）。
 *
 * 统一处理三件事：信封解包、错误码映射、凭据携带。任何绕过它的 `fetch("/api/...")`
 * 都会漏掉其中一两件，于是错误提示各写各的。
 */

import { refreshServiceToken } from "@/lib/service-token";

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly requestId?: string,
    readonly details?: { field: string; issue: string }[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Envelope<T> = { data: T };
type PageEnvelope<T> = { data: T[]; meta: { nextCursor: string | null } };
type ErrorEnvelope = { error: { code: string; message: string; requestId?: string } };

const BASE = "/api/v1";

/**
 * 续签 service JWT（带去重）。
 *
 * 15 分钟的 token 会在用户正在操作时过期，所以遇到 401 自动换一次再重试。
 * 页面同时发多个请求时不该并发签一堆 token，所以共用同一个 in-flight promise。
 */
let refreshInFlight: Promise<void> | null = null;

function refreshOnce(): Promise<void> {
  if (!refreshInFlight) {
    refreshInFlight = refreshServiceToken().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/** GET 遇到 UPSTREAM_FAILED 退避重试一次（上游抖动很常见，不值得让用户手动重试）。 */
const RETRY_DELAY_MS = 400;
const RETRYABLE_CODES = new Set(["UPSTREAM_FAILED"]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "INTERNAL";
  let message = "出错了，请稍后再试";
  let requestId: string | undefined;

  try {
    const body = (await response.json()) as ErrorEnvelope;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      requestId = body.error.requestId;
    }
  } catch {
    // 非 JSON 响应（网关错误页等）：保留兜底文案，不要把 HTML 塞进 Error.message。
  }

  return new ApiError(code, message, response.status, requestId);
}

async function request<T>(path: string, init: RequestInit, retry: boolean): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (response.status === 401) {
    // 先在服务端续签一次；仍失败才把 401 抛给调用方。
    try {
      await refreshOnce();
    } catch {
      throw await parseError(response);
    }
    const retried = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
    if (!retried.ok) throw await parseError(retried);
    return unwrap<T>(retried);
  }

  if (!response.ok) {
    const error = await parseError(response);
    if (retry && init.method === undefined && RETRYABLE_CODES.has(error.code)) {
      await sleep(RETRY_DELAY_MS);
      return request<T>(path, init, false);
    }
    throw error;
  }

  return unwrap<T>(response);
}

async function unwrap<T>(response: Response): Promise<T> {
  const body = (await response.json()) as Envelope<T>;
  return body.data;
}

/** 取单对象：解包 `{data}`，失败抛 `ApiError`。 */
export async function apiFetch<T>(
  path: string,
  init: RequestInit & { idempotencyKey?: string } = {},
): Promise<T> {
  const { idempotencyKey, ...rest } = init;
  const headers: Record<string, string> = { ...((rest.headers as Record<string, string>) ?? {}) };
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

  // 写操作**不自动重试**：幂等由 service 的业务键保证，前端重试只会放大冲突。
  const isRead = rest.method === undefined || rest.method === "GET";
  return request<T>(path, { ...rest, headers }, isRead);
}

/** 取列表页：连同 `meta.nextCursor` 一起返回。 */
export async function apiFetchPage<T>(
  path: string,
  init: RequestInit = {},
): Promise<{ data: T[]; meta: { nextCursor: string | null } }> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as PageEnvelope<T>;
}

/** 读 SSE：`meta → delta → result → done`（`docs/tech/frontend.md` §6）。 */
export async function streamSSE(
  path: string,
  body: unknown,
  on: {
    meta?: (data: unknown) => void;
    delta?: (text: string) => void;
    result?: (data: unknown) => void;
    done?: () => void;
  },
): Promise<void> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) throw await parseError(response);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE 以空行分隔事件；最后一段可能不完整，留在 buffer 里等下一次。
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      const event = /^event: (.+)$/m.exec(chunk)?.[1];
      const dataLine = /^data: (.+)$/m.exec(chunk)?.[1];
      if (!event || dataLine === undefined) continue;
      const parsed: unknown = JSON.parse(dataLine);
      if (event === "meta") on.meta?.(parsed);
      else if (event === "delta") on.delta?.(String((parsed as { text?: string }).text ?? ""));
      else if (event === "result") on.result?.(parsed);
    }
  }
  on.done?.();
}
