# web 层规约（Next.js 页面与认证）

> **契约查 `docs/tech/frontend.md`**（逐页五种状态、组件复用、令牌传递、错误码映射）。
> 本文只写"改 `web/` 代码时要注意什么"。

## 目录职责

```
web/
├── src/
│   ├── app/
│   │   ├── page.tsx                 落地页（公开）
│   │   ├── (auth)/login|register/   登录 / 注册（公开）
│   │   ├── (dashboard)/**          15 个受保护页面中的 12 个（共用导航布局）
│   │   └── api/
│   │       ├── auth/[...all]/       Better Auth 路由（web 唯一的认证入口）
│   │       └── service-token/       签发 15 分钟 service JWT
│   ├── components/                  nav-bar / api-section / 三个状态组件
│   ├── lib/                         取数与认证的地基
│   └── proxy.ts                     受保护路由守卫
└── tests/                           vitest（api.ts 与错误码映射）
```

**边界**：web 只做"渲染页面 + 管登录"。业务数据全走 `/api/v1/*`。
`grep -rn "prisma" web/src` 必须为空。

## Pre-Development Checklist

- [ ] **这个数据该由谁取？** 业务数据一律 `apiFetch` → `/api/v1/*`。web 不直连业务表。
- [ ] **契约在 `docs/tech/api/` 里对得上吗？** 字段名是 snake_case，不做 camelCase 转换。
- [ ] **五种状态写了吗？** 初始 / 触发 / 成功 / 失败 / 空（`docs/tech/frontend.md` §3 逐页有表）。
      空数据**不画空坐标轴**，给引导文案。
- [ ] **用了 `ApiSection` 还是手写五态？** 手写容易漏掉失败态 → 线上白屏。
- [ ] **改了 `lib/api.ts` 的导出吗？** 它是取数唯一出口，改动影响所有页面。
- [ ] **新页面要加进导航吗？** 加在 `components/nav-bar.tsx` 的 `LINKS`。

## Quality Check

```
cd web
npm run check     # typecheck → lint → vitest，三步都必须绿
```

`npm run check` 是 CI 里 `web-check` 的前三步。**再跑一次 `npm run build`**——
它抓到过 `npm run check` 完全看不见的两类问题（R000 实测）：

| 只有构建能发现 | 症状 |
|---|---|
| `useSearchParams()` 没包 `Suspense` | 构建期预渲染直接报错退出（不是警告） |
| `reactCompiler: true` 但缺 `babel-plugin-react-compiler` | `Failed to resolve package` |

构建用占位环境变量即可：它不连库。Better Auth 的 "Could not validate the database schema"
只是 ERROR 日志，不影响构建成功（看到它不用慌）。

`npm run check` 与 `npm run build` 都在 `web-check` 里跑。

## 三条硬规则

### 1. 页面不得自己拼 `fetch`

取数只有两个出口：`lib/api.ts`（业务数据）与 `lib/service-token.ts`（令牌与登出）。
这条可以直接验证：

```bash
# 期望只有 lib/api.ts 与 lib/service-token.ts 两个文件
grep -rn 'fetch("/api' web/src
```

绕过它们的代价是真实的：漏掉 `credentials: "include"`（cookie 不随请求走 → 全部 401）、
漏掉 401 续签、或把 HTML 错误页当成 JSON 解析后把乱码显示给用户。

### 2. 错误文案由 web 映射

service 只返回 `code`，中文文案在 `lib/error-messages.ts`。**不要把 `code` 直接显示给用户**，
也不要在 service 里做文案本地化。

未知 code 必须落到兜底文案而不是抛出——后端新增错误码时前端不能白屏。

### 3. 客户端取数

除登录态与 `/meta` 外，页面都是客户端组件取数。理由是 service 是独立进程，
服务端渲染就得再造一条"带凭据调 service"的路径（两跳、两份超时与错误处理）。

## 认证链路

```
登录 → Better Auth 写 session cookie
     → POST /api/service-token 用私钥签 15 分钟 RS256 JWT
     → 写 httpOnly cookie `summer_service_jwt`
     → 后续 /api/v1/* 自动带 cookie，service 验签取 sub=user_id
```

- 登录/注册成功后**立刻**换 service token，否则第一个业务请求先吃一个 401。
- `lib/api.ts` 遇到 401 会自动续签一次再重试；并发的请求共用同一个 in-flight promise
  （否则会同时签一堆 token）。
- `Authorization: Bearer` 在 service 侧**优先于** cookie，供 CLI/CI 覆盖。
- 登出要清两个：Better Auth 会话 + `summer_service_jwt`。

## 路由守卫

`src/proxy.ts`（Next 16 把 `middleware.ts` 改名而来，函数名也叫 `proxy`，构建时会被重命名为
`middleware.js`）。它**只校验会话 cookie 存在**——这是体验优化，不是安全边界。
真正的鉴权在 service 验签。

静态资源不参与重定向：把一个 `.mp4` 请求重定向成 HTML，浏览器会报"无法播放"。
`api/` 也排除在外，让 service 返回统一错误码而不是被重定向。

## 测试约定

`web/tests/` 用 vitest + node 环境，覆盖 `lib/`：

- `api.test.ts`：信封解包、`/api/v1` 前缀、cookie 携带、错误码解析、401 续签重试、
  写操作不重试、游标分页。
- `error-messages.test.ts`：九个错误码都有中文文案且**不含英文码名**。

`next/navigation` 与 React 组件的测试需要额外环境，R000 不引入——页面逻辑薄到
类型检查 + 手工验收足够。

## 常见错误

| 症状 | 原因 | 怎么做 |
|---|---|---|
| 所有接口 401，但 curl 正常 | `fetch` 漏了 `credentials: "include"` | 走 `apiFetch` |
| 打开页面被重定向到登录，已登录也如此 | `proxy.ts` 的 cookie 名不对 | Better Auth 的会话 cookie 名见 `proxy.ts` 的取值链 |
| 视频/图片请求变成 HTML | 静态资源被守卫重定向 | 保留 `proxy.ts` 里的扩展名判断 |
| `npm run lint` 报 `next is not a function` | eslint 配置导入方式不对 | 照 `eslint.config.mjs` 用 `defineConfig` + 展开 |
| effect 里同步 `setState` 报错 | React Compiler 的新规则 | 从 props/state 派生，别在 effect 里同步写状态（见 `lib/use-api.ts` 的做法） |
| `next build` 报 `useSearchParams() should be wrapped in a suspense boundary` | 客户端组件直接用了 `useSearchParams` | 把用到它的部分拆成子组件，外层包 `<Suspense>`（见 `(auth)/login/page.tsx`） |
| `next build` 报 `Failed to resolve package babel-plugin-react-compiler` | `next.config.ts` 开了 `reactCompiler` 但没装插件 | `npm i -D babel-plugin-react-compiler` |
