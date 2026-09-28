# Summer Checkin

学习打卡与复盘平台：每日打卡、学习计划、AI 巡检与复盘。

> 本项目是 [gdut4140/summer-checkin](https://github.com/gdut4140/summer-checkin) 的二次开发，
> 沿用其领域设计与数据模型，架构重写为前后端分离，遵循原项目的 MIT 协议。

## 当前状态

**R000（双服务骨架）已完成，业务功能尚未实现。**

两个服务能跑、能登录、能连库，页面能打开并显示空态；打卡、计划、巡检、复盘的写接口还没做。
排期见 `docs/PRD.md`。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS v4 |
| 前端认证 | Better Auth |
| 后端 | FastAPI、Python 3.12、SQLAlchemy 2.0 (async)、Alembic、Pydantic v2 |
| 数据库 | PostgreSQL 16 + pgvector |
| AI | 模型池（多档位降级、限流冷却、token 记账） |
| 部署 | Docker Compose（web / service / db / nginx）+ nginx 路径分流 |
| 质量 | ruff、pytest、ESLint、tsc、vitest |

## 项目结构

```
├── service/          FastAPI 领域服务
│   ├── app/
│   │   ├── core/     配置、鉴权、统一响应与错误码、日志、分页
│   │   ├── db/       声明基类、async 会话
│   │   ├── models/   31 张表的 SQLAlchemy 模型
│   │   ├── schemas/  对外 JSON 的 Pydantic 模型
│   │   ├── api/v1/   路由
│   │   └── llm/      模型池
│   ├── alembic/      迁移（DDL 的唯一来源）
│   └── tests/
├── web/              Next.js 前端
│   └── src/
│       ├── app/      15 个页面 + 认证路由
│       ├── components/
│       ├── lib/      api.ts（取数出口）、错误码映射、Better Auth
│       └── proxy.ts  受保护路由守卫
├── infra/            Dockerfile、compose、nginx、建库脚本
├── docs/             PRD 与技术文档
└── .trellis/         需求任务与编码规约
```

服务分离部署，nginx 按路径分流：

```
浏览器 → nginx ─┬─ / 与 /api/auth/*  → web（Next.js）
                └─ /api/v1/*         → service（FastAPI）→ PostgreSQL + pgvector
```

## 本地运行

需要 Node 22、Python 3.12 与 Docker。

```bash
# 1. 起数据库
docker compose -f infra/docker-compose.dev.yml up -d

# 2. 配置环境变量（模板见 .env.example）
#    注意：两个服务都不读根目录的 .env
cp .env.example service/.env        # SUMMER_* 那些
cp .env.example web/.env.local      # DATABASE_URL / BETTER_AUTH_* / SUMMER_JWT_PRIVATE_KEY

# 3. service（普通 venv + pip，`-i` 指定镜像源）
cd service
python -m venv .venv                            # Windows: py -3.12 -m venv .venv
source .venv/bin/activate                       # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -i https://mirrors.aliyun.com/pypi/simple/
alembic upgrade head
uvicorn app.main:app --reload                   # :8000

# 4. web（另开终端）
cd web
npm ci
npm run dev                             # :3000
```

## 测试

```bash
cd service
source .venv/bin/activate                       # Windows: .venv\Scripts\activate
ruff check . && ruff format --check . && pytest    # 93 passed
cd ../web && npm run check                         # typecheck + lint + vitest
```

## 文档

- `docs/PRD.md` — 做什么
- `docs/tech/` — 怎么做（跨需求契约的唯一事实来源，改代码前先读）
- `.trellis/spec/` — 分层编码规约与校验命令

## 协议

[MIT](./LICENSE)
