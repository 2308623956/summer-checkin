import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, apiFetchPage } from "@/lib/api";

/** 造一个 fetch 返回值。 */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const originalFetch = globalThis.fetch;

/** 记录调用参数的 fetch 替身：显式给参数类型，否则 `mock.calls[0][1]` 无法索引。 */
function mockFetch(handler: (url: string, init?: RequestInit) => Promise<Response>) {
  const spy = vi.fn(handler);
  globalThis.fetch = spy as unknown as typeof fetch;
  return spy;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("apiFetch", () => {
  it("unwraps the data envelope", async () => {
    mockFetch(async () => jsonResponse({ data: { status: "ok" } }));
    await expect(apiFetch("/healthz")).resolves.toEqual({ status: "ok" });
  });

  it("requests the /api/v1 prefix", async () => {
    const spy = mockFetch(async () => jsonResponse({ data: {} }));
    await apiFetch("/meta");
    expect(spy.mock.calls[0][0]).toBe("/api/v1/meta");
  });

  it("always sends credentials so the httpOnly cookie travels", async () => {
    const spy = mockFetch(async () => jsonResponse({ data: {} }));
    await apiFetch("/meta");
    expect(spy.mock.calls[0][1]?.credentials).toBe("include");
  });

  it("throws ApiError carrying code, status and requestId", async () => {
    mockFetch(async () =>
      jsonResponse({ error: { code: "FORBIDDEN", message: "没有权限", requestId: "req-7" } }, 403),
    );

    await expect(apiFetch("/checkins")).rejects.toMatchObject({
      code: "FORBIDDEN",
      status: 403,
      requestId: "req-7",
    });
  });

  it("falls back to a sane error when the body is not JSON", async () => {
    mockFetch(async () => new Response("<html>502 Bad Gateway</html>", { status: 502 }));

    const error = await apiFetch("/checkins").catch((cause: unknown) => cause);
    expect(error).toBeInstanceOf(ApiError);
    // 不要把 HTML 塞进 message：用户看到的应该是人话。
    expect((error as ApiError).message).toBe("出错了，请稍后再试");
  });

  it("sends Idempotency-Key when provided", async () => {
    const spy = mockFetch(async () => jsonResponse({ data: {} }));
    await apiFetch("/approvals", { method: "POST", idempotencyKey: "key-1" });

    const headers = spy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toBe("key-1");
  });

  it("does not retry a failed write", async () => {
    const spy = mockFetch(async () =>
      jsonResponse({ error: { code: "UPSTREAM_FAILED", message: "上游挂了" } }, 502),
    );

    await expect(apiFetch("/checkins", { method: "POST" })).rejects.toBeInstanceOf(ApiError);
    // 写操作重试会放大冲突，幂等由 service 保证。
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("refreshes the service token once on 401 and retries", async () => {
    let call = 0;
    const spy = mockFetch(async (url: string) => {
      call += 1;
      if (url === "/api/service-token") return jsonResponse({ data: { expiresIn: 900 } });
      return call === 1
        ? jsonResponse({ error: { code: "AUTH_REQUIRED", message: "登录已过期" } }, 401)
        : jsonResponse({ data: { ok: true } });
    });

    await expect(apiFetch("/meta")).resolves.toEqual({ ok: true });
    expect(spy.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/meta",
      "/api/service-token",
      "/api/v1/meta",
    ]);
  });

  it("throws AUTH_REQUIRED when the refresh itself fails", async () => {
    mockFetch(async (url: string) =>
      url === "/api/service-token"
        ? jsonResponse({ error: { code: "AUTH_REQUIRED", message: "请先登录" } }, 401)
        : jsonResponse({ error: { code: "AUTH_REQUIRED", message: "登录已过期" } }, 401),
    );

    await expect(apiFetch("/meta")).rejects.toMatchObject({ code: "AUTH_REQUIRED" });
  });
});

describe("apiFetchPage", () => {
  it("returns data together with the cursor meta", async () => {
    mockFetch(async () => jsonResponse({ data: [{ id: "a" }], meta: { nextCursor: "next-1" } }));

    await expect(apiFetchPage("/checkins")).resolves.toEqual({
      data: [{ id: "a" }],
      meta: { nextCursor: "next-1" },
    });
  });

  it("handles an empty page", async () => {
    mockFetch(async () => jsonResponse({ data: [], meta: { nextCursor: null } }));

    await expect(apiFetchPage("/plans")).resolves.toEqual({
      data: [],
      meta: { nextCursor: null },
    });
  });
});
