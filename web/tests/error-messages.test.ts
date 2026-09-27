import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { actionFor, isApiError, messageFor } from "@/lib/error-messages";

describe("messageFor", () => {
  it("maps every documented error code to Chinese copy", () => {
    const codes = [
      "AUTH_REQUIRED",
      "FORBIDDEN",
      "NOT_FOUND",
      "VALIDATION_FAILED",
      "CONFLICT",
      "RATE_LIMITED",
      "QUOTA_EXCEEDED",
      "UPSTREAM_FAILED",
      "INTERNAL",
    ];
    for (const code of codes) {
      const message = messageFor(new ApiError(code, "raw", 400));
      // 绝不把英文码名显示给用户。
      expect(message).not.toContain(code);
      expect(message.length).toBeGreaterThan(0);
    }
  });

  it("falls back for an unknown code", () => {
    expect(messageFor(new ApiError("SOMETHING_NEW", "raw", 400))).toBe("出错了，请稍后再试");
  });

  it("falls back for a non-ApiError", () => {
    expect(messageFor(new Error("boom"))).toBe("出错了，请稍后再试");
    expect(messageFor(undefined)).toBe("出错了，请稍后再试");
  });
});

describe("actionFor", () => {
  it("routes auth failures to re-login", () => {
    expect(actionFor(new ApiError("AUTH_REQUIRED", "x", 401))).toBe("relogin");
  });

  it("offers a retry for upstream failures", () => {
    expect(actionFor(new ApiError("UPSTREAM_FAILED", "x", 502))).toBe("retry");
  });

  it("refreshes data on conflict", () => {
    expect(actionFor(new ApiError("CONFLICT", "x", 409))).toBe("refresh");
  });

  it("cools down the button when rate limited", () => {
    expect(actionFor(new ApiError("RATE_LIMITED", "x", 429))).toBe("cooldown");
  });

  it("shows a banner when quota is exhausted", () => {
    expect(actionFor(new ApiError("QUOTA_EXCEEDED", "x", 429))).toBe("banner");
  });
});

describe("isApiError", () => {
  it("narrows ApiError", () => {
    expect(isApiError(new ApiError("INTERNAL", "x", 500))).toBe(true);
    expect(isApiError(new Error("x"))).toBe(false);
    expect(isApiError(null)).toBe(false);
  });
});
