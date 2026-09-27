#!/usr/bin/env bash
# deploy.sh — Summer Checkin Docker 容器管理脚本
#
# 用法：
#   ./deploy.sh             启动已构建的服务
#   ./deploy.sh start       启动服务，不重新构建镜像
#   ./deploy.sh build       构建并启动服务
#   ./deploy.sh rebuild     无缓存重建并重启服务
#   ./deploy.sh stop        停止并移除容器（不删除数据卷）
#   ./deploy.sh logs [服务] 跟踪全部日志，或只跟踪指定服务
#   ./deploy.sh status      查看服务状态
#   ./deploy.sh validate    校验 .env 和 Compose 配置
#   ./deploy.sh help        显示帮助

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
SERVICES=(db service web nginx)

usage() {
    grep '^#   ' "$0" | sed 's/^#   /  /'
}

require_docker_compose() {
    if ! command -v docker >/dev/null 2>&1; then
        echo "[ERROR] 未找到 docker，请先安装 Docker Desktop 或 Docker Engine。" >&2
        exit 1
    fi
    if ! docker compose version >/dev/null 2>&1; then
        echo "[ERROR] 需要 Docker Compose v2（docker compose）。" >&2
        exit 1
    fi
}

compose() {
    docker compose -f "$COMPOSE_FILE" --env-file "$PROJECT_ROOT/.env" "$@"
}

validate_deployment() {
    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        echo "[ERROR] 未找到 .env，请先复制 .env.example 并填写配置。" >&2
        echo "  cp .env.example .env" >&2
        exit 1
    fi
    
    # 检查必需的环境变量
    local missing=()
    for var in POSTGRES_PASSWORD JWT_SECRET SUMMER_CRON_SECRET BETTER_AUTH_SECRET; do
        if ! grep -q "^${var}=" "$PROJECT_ROOT/.env" || grep -q "^${var}=CHANGE_ME" "$PROJECT_ROOT/.env"; then
            missing+=("$var")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "[ERROR] .env 中缺失或未配置以下必需变量：${missing[*]}" >&2
        echo "  请编辑 .env 并填入真实密钥。" >&2
        exit 1
    fi
    
    compose config --quiet
    echo "[INFO] Docker Compose 配置和 .env 校验通过。"
}

wait_for_healthy() {
    local service container_id status attempt
    for service in "$@"; do
        container_id="$(compose ps -q "$service" 2>/dev/null || true)"
        if [[ -z "$container_id" ]]; then
            echo "[ERROR] 未找到服务容器：$service" >&2
            exit 1
        fi
        echo "[INFO] 等待 $service 健康检查..."
        for attempt in $(seq 1 30); do
            status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || echo "unknown")"
            if [[ "$status" == "healthy" || "$status" == "running" ]]; then
                echo "[INFO] $service 已就绪"
                break
            fi
            if [[ "$status" == "unhealthy" || "$status" == "exited" || "$status" == "dead" ]]; then
                echo "[ERROR] 服务未能启动：$service（$status）" >&2
                compose logs --tail 50 "$service" >&2
                exit 1
            fi
            sleep 2
        done
        if [[ "$status" != "healthy" && "$status" != "running" ]]; then
            echo "[ERROR] 等待服务健康检查超时：$service（$status）" >&2
            compose logs --tail 50 "$service" >&2
            exit 1
        fi
    done
}

run_migrations() {
    echo "[INFO] 运行数据库迁移..."
    compose run --rm service /app/.venv/bin/alembic upgrade head
    echo "[INFO] 迁移完成"
}

show_endpoints() {
    local http_port
    http_port="${HTTP_PORT:-80}"
    
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        http_port="$(grep '^HTTP_PORT=' "$PROJECT_ROOT/.env" | cut -d= -f2 | tr -d '\r' | tr -d '"' | tr -d "'" || echo "80")"
    fi
    
    echo ""
    echo "============================================"
    echo "  Summer Checkin 已启动"
    echo "============================================"
    echo "  应用：http://127.0.0.1:${http_port}"
    echo "  后端 API：http://127.0.0.1:${http_port}/api/v1/meta"
    echo "  健康检查：http://127.0.0.1:${http_port}/api/v1/healthz"
    echo "============================================"
}

start_services() {
    validate_deployment
    
    # 先启动数据库
    compose up -d --no-build db
    wait_for_healthy db
    
    # 运行迁移（生产环境）
    if grep -q '^SUMMER_ENV=production' "$PROJECT_ROOT/.env" 2>/dev/null; then
        run_migrations
    else
        echo "[INFO] 开发环境，跳过迁移（服务启动时自动执行）"
    fi
    
    # 启动其他服务
    compose up -d --no-build service web nginx
    wait_for_healthy service web
    
    show_endpoints
}

build_services() {
    validate_deployment
    compose build service web
    start_services
}

rebuild_services() {
    validate_deployment
    compose down --remove-orphans
    compose build --no-cache service web
    start_services
}

case "${1:-}" in
    ""|start)
        require_docker_compose
        [[ $# -le 1 ]] || { echo "[ERROR] start 不接受额外参数。" >&2; usage; exit 1; }
        start_services
        ;;
    build)
        require_docker_compose
        [[ $# -eq 1 ]] || { echo "[ERROR] build 不接受额外参数。" >&2; usage; exit 1; }
        build_services
        ;;
    rebuild)
        require_docker_compose
        [[ $# -eq 1 ]] || { echo "[ERROR] rebuild 不接受额外参数。" >&2; usage; exit 1; }
        rebuild_services
        ;;
    stop)
        require_docker_compose
        [[ $# -eq 1 ]] || { echo "[ERROR] stop 不接受额外参数。" >&2; usage; exit 1; }
        compose down --remove-orphans
        echo "[INFO] 服务已停止（数据卷已保留）"
        ;;
    logs)
        require_docker_compose
        if [[ -n "${2:-}" ]]; then
            case "$2" in
                db|service|web|nginx) compose logs -f "$2" ;;
                *) echo "[ERROR] logs 只接受 db、service、web 或 nginx。" >&2; exit 1 ;;
            esac
        else
            compose logs -f "${SERVICES[@]}"
        fi
        ;;
    status)
        require_docker_compose
        compose ps "${SERVICES[@]}"
        ;;
    validate)
        require_docker_compose
        validate_deployment
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo "[ERROR] 未知参数：'${1:-}'" >&2
        usage
        exit 1
        ;;
esac
