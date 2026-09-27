# service 镜像：uv 官方组合镜像（Python 3.12 + uv，Debian slim，glibc 与 python:3.12-slim 同源）。
# 单 worker：agent 任务重、并发低；要横向扩展时再拆调度（architecture.md §6）。
FROM docker.1ms.run/astral/uv:python3.12-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    # 国内构建走清华 PyPI 镜像
    UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
    # 镜像限速时 30s 默认超时太短，大轮子（asyncpg/cryptography）容易下到一半被掐
    UV_HTTP_TIMEOUT=120

WORKDIR /app

# 先只拷依赖清单：改代码不会让依赖层缓存失效。
# --mount=type=cache：uv 的下载缓存跨构建持久化，这层重建时也只下增量。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY service/ ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 非 root 运行：容器被攻破时不要连带拿到宿主机的 root。
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 注意：这里**不跑迁移**。迁移由 infra/deploy.sh 显式执行，
# 否则多实例同时启动会并发跑迁移（architecture.md §6）。
# 端口从环境变量读取，默认 8000
CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8000}"]
