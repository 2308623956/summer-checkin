# service 镜像：官方 python:3.12-slim + 普通 venv + pip（不用 uv：pip 安装时可以直接
# 指定镜像源，也不会像 uv.lock 那样把源锁死在 pypi.org）。
# 单 worker：agent 任务重、并发低；要横向扩展时再拆调度（architecture.md §6）。
FROM docker.1ms.run/library/python:3.12-slim AS base

# pip 源：默认阿里云公网镜像（本地与 CI 都能用）；阿里云 ECS 上构建时改成内网源
# http://mirrors.cloud.aliyuncs.com/pypi/simple/ 更快——在 .env 里设 PIP_INDEX_URL，
# infra/docker-compose.yml 会把它作为 build arg 传进来。
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# 先只拷依赖清单：改代码不会让依赖层缓存失效。
# --mount=type=cache：pip 的下载缓存跨构建持久化，这层重建时也只下增量。
# 内网镜像源是 http 的，pip 会忽略"非安全源"，所以按 URL 取主机名加进白名单
# （https 源加白名单也无副作用）。
COPY service/requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /app/.venv \
 && pip_host="$(printf '%s' "$PIP_INDEX_URL" | sed -e 's|^[^/]*//||' -e 's|/.*$||')" \
 && /app/.venv/bin/python -m pip install \
        --index-url "$PIP_INDEX_URL" \
        --trusted-host "$pip_host" \
        -r requirements.txt

COPY service/ ./

# 非 root 运行：容器被攻破时不要连带拿到宿主机的 root。
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 注意：这里**不跑迁移**。迁移由 infra/deploy.sh 显式执行，
# 否则多实例同时启动会并发跑迁移（architecture.md §6）。
# 端口从环境变量读取，默认 8000
CMD ["/bin/sh", "-c", "/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${SERVICE_PORT:-8000}"]
