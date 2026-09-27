import { betterAuth } from "better-auth";
import { Kysely, PostgresDialect } from "kysely";
import { Pool } from "pg";

/**
 * Better Auth 只负责**认证**，只碰四张认证表（user / session / account / verification）。
 * 业务数据归 service，表结构归 Alembic（ADR-001）。
 *
 * 两个容易踩的点：
 * 1. 表名与列名是 snake_case（`emailVerified` / `createdAt`），必须显式映射，
 *    否则 Better Auth 会去找 `"emailVerified"` 这样的列并报 "column does not exist"。
 * 2. 参考实现里的 `user.create.after → cloneGuideTemplates` 已删除（`design.md` D14）：
 *    引导模板属于业务数据，写它要走 service，不能让认证钩子越界写业务表。
 */

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

// Better Auth 的字段名是 camelCase，表里是 snake_case，这里做唯一一处映射。
const db = new Kysely<Record<string, never>>({
  dialect: new PostgresDialect({ pool }),
});

export const auth = betterAuth({
  database: {
    db,
    type: "postgres",
  },
  emailAndPassword: {
    enabled: true,
  },
  // 构建时可能没有环境变量（worker 进程），给默认值避免报错
  secret: process.env.BETTER_AUTH_SECRET || "build-time-placeholder-secret-min-32-chars-long",
  baseURL: process.env.BETTER_AUTH_URL || "http://localhost:3000",
  user: {
    fields: {
      emailVerified: "email_verified",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
    additionalFields: {
      bio: { type: "string", required: false },
      theme: { type: "string", required: false, defaultValue: "system" },
      vip: { type: "boolean", required: false, defaultValue: false },
    },
  },
  session: {
    fields: {
      userId: "user_id",
      expiresAt: "expires_at",
      ipAddress: "ip_address",
      userAgent: "user_agent",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
    cookieCache: {
      enabled: true,
      // 5 分钟：避免跨标签页缓存不一致
      maxAge: 5 * 60,
    },
  },
  account: {
    fields: {
      userId: "user_id",
      providerId: "provider_id",
      accountId: "account_id",
      accessToken: "access_token",
      refreshToken: "refresh_token",
      accessTokenExpiresAt: "access_token_expires_at",
      refreshTokenExpiresAt: "refresh_token_expires_at",
      idToken: "id_token",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  verification: {
    fields: {
      expiresAt: "expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  trustedOrigins: [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    process.env.BETTER_AUTH_URL ?? "",
  ].filter(Boolean),
});
