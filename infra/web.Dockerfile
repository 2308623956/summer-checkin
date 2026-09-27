# web 镜像：多阶段构建，运行时用 standalone 产物。
FROM node:22-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY web/ ./
# standalone 输出要求 next.config.ts 里 `output: "standalone"`。
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

# standalone 只带运行必需的依赖与产物，镜像比整份 node_modules 小一个量级。
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# 端口从环境变量读取，默认 3000
CMD ["sh", "-c", "PORT=${WEB_PORT:-3000} HOSTNAME=0.0.0.0 node server.js"]
