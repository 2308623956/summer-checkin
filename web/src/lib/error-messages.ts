/**
 * 错误码 → 用户文案。**一处维护**，页面不写自己的错误文案
 * （`docs/tech/frontend.md` §7）。
 *
 * 文案原则（`frontend.md` §9）：不用惩罚式语气；失败要给出可行动的下一步。
 */

import { ApiError } from "@/lib/api";

type Mapping = {
  message: string;
  /** 页面据此决定行为：跳登录、刷新数据、禁用按钮… */
  action: "relogin" | "toast" | "notFound" | "field" | "refresh" | "cooldown" | "banner" | "retry" | "none";
};

const MESSAGES: Record<string, Mapping> = {
  AUTH_REQUIRED: { message: "登录已过期，请重新登录", action: "relogin" },
  FORBIDDEN: { message: "没有权限做这件事", action: "toast" },
  NOT_FOUND: { message: "内容不存在或已被删除", action: "notFound" },
  VALIDATION_FAILED: { message: "请检查填写的内容", action: "field" },
  CONFLICT: { message: "这件事已经处理过了", action: "refresh" },
  RATE_LIMITED: { message: "操作太频繁，请稍后再试", action: "cooldown" },
  QUOTA_EXCEEDED: { message: "今日 AI 额度已用完", action: "banner" },
  UPSTREAM_FAILED: { message: "模型或存储暂时不可用", action: "retry" },
  INTERNAL: { message: "出错了，请稍后再试", action: "none" },
};

const FALLBACK: Mapping = { message: "出错了，请稍后再试", action: "none" };

/** 取用户文案。未知错误码也走兜底，绝不把英文码名显示给用户。 */
export function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return MESSAGES[error.code]?.message ?? FALLBACK.message;
  }
  return FALLBACK.message;
}

export function actionFor(error: unknown): Mapping["action"] {
  if (error instanceof ApiError) {
    return MESSAGES[error.code]?.action ?? FALLBACK.action;
  }
  return FALLBACK.action;
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
