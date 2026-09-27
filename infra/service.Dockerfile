# service 镜像：python:3.12-slim + uv。
# 单 worker：agent 任务重、并发低；要横向扩展时再拆调度（architecture.md §6）。
FROM docker.1ms.run/library/python:3.12.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    # 国内构建走清华 PyPI 镜像
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

# uv 从官方镜像拷进来，避免在构建期 pip install uv。
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv

WORKDIR /app

# 先只拷依赖清单：改代码不会让依赖层缓存失效。
COPY service/pyproject.toml service/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY service/ ./
RUN uv sync --frozen --no-dev

# 非 root 运行：容器被攻破时不要连带拿到宿主机的 root。
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 注意：这里**不跑迁移**。迁移由 infra/deploy.sh 显式执行，
# 否则多实例同时启动会并发跑迁移（architecture.md §6）。
# 端口从环境变量读取，默认 8000
CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8000}"]
