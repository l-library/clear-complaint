# ClearComplaint 开发约定

面向全体成员与 AI agent 的工程约定。产品背景与交付计划见 [docs/PLAN.md](docs/PLAN.md)，赛题与平台边界见 [docs/赛题调研.md](docs/赛题调研.md)。英文镜像在 [AGENTS.md](AGENTS.md)，两份必须同一次提交一起改。

## 1. 项目总体结构

清诉是前后端分离的应用：`frontend/` 用 uni-app 一套代码编译到 H5 与微信小程序，`backend/` 是 FastAPI 单体，Postgres 跑在 Docker 里。仓库是 monorepo。

```
.
├── backend/                        FastAPI 单体，uv 管理依赖与虚拟环境
│   ├── app/
│   │   ├── main.py                 应用工厂，/api 前缀只在这里出现
│   │   ├── core/config.py          配置（pydantic-settings，读 .env）
│   │   ├── common/
│   │   │   ├── api.py              ApiResponse、ok()/error()
│   │   │   ├── codes.py            ErrorCode 枚举
│   │   │   ├── errors.py           BizException、全局异常处理器
│   │   │   └── web.py              /ping、/health
│   │   ├── db/
│   │   │   ├── base.py             DeclarativeBase
│   │   │   └── session.py          引擎、会话工厂、get_session 依赖
│   │   ├── api/__init__.py         路由汇总，只在 main.py 挂一次前缀
│   │   └── <领域>/                 每个业务领域一个包，内部自带 router/service/schema/models
│   ├── alembic/                    迁移脚本，versions/ 下 V1 起
│   ├── alembic.ini                 连接串不写在这里，由 env.py 从配置读
│   ├── tests/                      与被测模块同构的测试
│   ├── pyproject.toml              依赖、ruff、mypy、pytest 配置
│   └── .env.example                复制成 .env 使用
├── frontend/                       uni-app 工程，H5 与微信小程序
│   ├── src/pages/                  页面，在 src/pages.json 注册
│   ├── src/api/                    按领域拆的请求函数
│   ├── src/request/                H5 与小程序共用的请求封装
│   ├── src/pages.json              路由、tabBar、分包
│   ├── src/manifest.json           微信 appid 等分端配置
│   ├── scripts/                    Node 校验脚本：check:interactions（进 CI）、check:live（手动）
│   ├── vite.config.ts              H5 开发时的 /api 代理（指向 8000）
│   └── pnpm-workspace.yaml         pnpm 12 的全部设置：依赖构建白名单与 nodeLinker
├── experiment/                     阶段一研究工件：独立 uv 项目，不 import 后端
│   ├── corpus/                     指南片段、冻结向量、候选词表、科室表、红旗清单
│   ├── cases/                      病例、五个变体、金标准、签核记录
│   ├── harness/                    归一化、红旗、检索、引用与模板校验、模型客户端
│   ├── arms/                       四个实验臂的提示词与开关快照
│   ├── runs/                       原始响应与参数，只追加
│   ├── analysis/                   指标、bootstrap、figures/
│   └── handoff/                    约束规格书与冻结样本，阶段二验收用
├── docs/                           PLAN.md、stage1.md、赛题调研.md，以后放材料与实验数据
├── docker-compose.yml              本地 Postgres 16
├── start-local.ps1                 Windows 辅助脚本：Docker、Postgres、后端、H5（见第 2 节）
├── .github/                        CI 与 issue 模板
├── .editorconfig                   编辑格式规则（机器强制）
├── .gitattributes                  换行规则（机器强制）
├── CONVENTION.md                   本文件，中文
├── AGENTS.md                       英文镜像
├── CLAUDE.md                       指向 AGENTS.md
└── README.md                       产品背景与技术栈
```

- 后端按功能分包，不按 `routers/` `services/` `models/` 这类技术层平铺。一个领域一个包，跨包只依赖 `common`、`db` 和对方的 service。
- `experiment/` 是阶段一的研究工件，独立 uv 项目，不 import `backend/`，后端也不依赖它。阶段二需要它的归一化、红旗或引用核验逻辑时复制副本进 `backend/app/`，两处各自独立运行，不合并成一个包。
- 领域包内部约定：`router.py` 放路由，`service.py` 放业务逻辑，`schema.py` 放请求响应模型，`models.py` 放 ORM 模型。没有的部分不建空文件。
- 前端页面放 `src/pages/<模块>/<页面>.vue`，组件以 `Q` 开头。

## 2. 开发环境

- Python 3.14，由 uv 管理。`backend/.python-version` 已钉版本，`uv sync` 会自动准备解释器和虚拟环境，不需要手动 `python -m venv`。不要用系统 pip 装依赖。
- uv 0.13 及以上。所有依赖操作走 `uv add`、`uv add --dev`、`uv sync`，不要手改 `pyproject.toml` 里的版本号去对齐锁文件。
- Node 26 + pnpm 12。pnpm 12 只从 `frontend/pnpm-workspace.yaml` 读设置，不再读 `.npmrc`。其中两项都不能删：`allowBuilds` 放行依赖的 postinstall（否则 `pnpm install` 报 `ERR_PNPM_IGNORED_BUILDS`），`nodeLinker: hoisted` 换成扁平 node_modules（isolated 布局下 uni-app 的 rollup 解析不到 pinia 的传递依赖，`pnpm build:h5` 会失败）。
- Docker 与 Docker Compose，Postgres 只跑在容器里。Docker daemon 必须已经启动（`docker info` 能通），否则 compose 命令会直接失败。
- 应用进程不进容器：后端用 uvicorn，前端用 Vite dev server。理由见第 8 节。
- `start-local.ps1` 是 Windows 专用的一键启动脚本，命令见下表。它需要 `backend/.env`，保留现有数据库数据，H5 起在 5175（不是 `pnpm dev:h5` 的 5173），日志写到被 Git 忽略的 `.tools/runtime/`，不会停止不是它启动的进程。

| 命令 | 作用 |
| --- | --- |
| `docker compose up -d` | 启动 Postgres（5432），数据在命名卷 `clear-complaint-db-data` |
| `docker compose logs -f db` | 看数据库日志 |
| `docker compose down` / `down -v` | 停止，后者连数据一起删 |
| `./start-local.ps1` | 仅 Windows：启动 Docker、Postgres、后端与 H5 开发服务器（5175） |
| `cd backend && uv sync` | 安装依赖并准备虚拟环境 |
| `cd backend && uv run uvicorn app.main:app --reload` | 启动后端，8000，接口前缀 `/api` |
| `cd backend && uv run pytest` | 后端测试（需要 docker 里的 Postgres） |
| `cd backend && uv run alembic upgrade head` | 迁移到最新 |
| `cd backend && uv run alembic revision -m "说明"` | 新建迁移 |
| `cd frontend && pnpm install` | 安装前端依赖 |
| `cd frontend && pnpm dev:h5` | H5 开发服务器，5173，`/api` 已代理到 8000 |
| `cd frontend && pnpm dev:mp-weixin` | 小程序产物，用微信开发者工具打开 `dist/dev/mp-weixin` |
| `cd frontend && pnpm type-check` | vue-tsc 类型检查 |
| `cd frontend && pnpm check:interactions` | 离线校验鉴权、刷新、SSE 解析与对话流程，CI 会跑 |
| `cd frontend && pnpm check:live` | 针对本机运行中的服务做端到端联调，使用临时合成账号 |
| `cd frontend && pnpm build:h5` | 前端最小验证，提交前跟 type-check 一起跑 |
| `cd frontend && pnpm build:mp-weixin` | 小程序生产构建，产物在 `dist/build/mp-weixin` |

提交前后端跑 `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`，前端跑 `pnpm type-check && pnpm check:interactions && pnpm build:h5`，另外用 `git diff --check` 自查空白与换行问题。

## 3. Git 协作规范

### 3.1 分支模型（只有 main 和功能分支）

- `main`：稳定分支，任何时候都能跑起来。只接受 PR 合入，直推会被 GitHub 规则集拒绝（`push declined due to repository rule violations`）。
- `feat/<名称>`：功能分支，从 main 拉出，PR 合回 main 后**立即删除**。纯缺陷修复用 `fix/<名称>`。
- 命名用 kebab-case 英文短语，如 `feat/triage-card`、`fix/mp-proxy-loop`。
- 一个分支只承载一件事（一个功能或一个修复），做完即合，不长期挂账。

### 3.2 Commit 信息（Conventional Commits）

- 格式：`<type>(<scope>): <subject>`。type 与 subject 用**英文**，subject 用祈使句、不超过 72 字符、结尾不加句号；scope 可省略。
- type 取值：`feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore`。
- body（可选）说明**为什么**这么改，每行不超过 72 字符；footer 可写 `Closes #123`、`BREAKING CHANGE: ...`。
- 一个 commit 只做一件事，不要把无关的格式化改动混进功能 commit（见第 4 节）。

示例：

```
feat(triage): reject duplicate evidence indexes

The gate accepted the same index twice and produced a duplicated citation.
Closes #34.
```

### 3.3 PR

- 标题沿用 Conventional Commit 格式；描述至少写清：**动机（为什么）**、**改动内容**、**验证方式**（跑了哪些命令、手测了什么）。UI 改动附截图或录屏。
- 合并前要求：
  - GitHub 规则集要求 PR，且 `backend` 与 `frontend` 两个 check 必须通过。approve 数量当前设为 0，可以自己合自己的 PR；想强制 review 就改规则集，别只改这份文档；
  - 后端改动跑过 `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`，前端改动跑过 `pnpm type-check && pnpm check:interactions && pnpm build:h5`；
  - 涉及表结构的改动，从空库重放一遍迁移（`docker compose down -v && docker compose up -d` 后 `uv run alembic upgrade head`）；
  - CI（`.github/workflows/ci.yml`）两个 job 全绿：`backend` 跑 lint、format check、mypy、pytest，`frontend` 跑 `pnpm install --frozen-lockfile`、`type-check`、`check:interactions`、`build:h5`、`build:mp-weixin`。
- 合并方式：**merge commit**（保留提交历史），规则集只允许这一种，squash 与 rebase 会被拒绝。review 期间的修改直接在分支上追加 commit 或 force-push 均可，合并前不强制整理历史。
- 合并后删除功能分支；PR 描述或 commit footer 用 `Closes #N` 关联 issue。
- PR 保持小而聚焦，大改动拆成多个 PR。

## 4. 编码格式

- 所有文本文件统一 **UTF-8（无 BOM）+ LF**。唯一例外：`*.bat` / `*.cmd` 用 CRLF。
- 缩进用空格，宽度由 [.editorconfig](.editorconfig) 规定：Python 为 **4 空格**，前端（`*.ts` `*.vue` `*.js` `*.json`）与 YAML、Markdown 为 **2 空格**。
- 文件末尾保留一个空行；去掉行尾空白（Markdown 除外，行尾两个空格是硬换行）。
- [.editorconfig](.editorconfig) 与 [.gitattributes](.gitattributes) 是机器强制的规则：IDE 请开启 EditorConfig 支持；提交前可用 `git diff --check` 检查空白与换行问题。
- Python 的格式与 import 顺序由 `ruff format` 与 `ruff check --fix` 决定，不要手工对齐。
- 不要在同一个 commit 里做全文件格式化。

## 5. 一般编码须知

### 动手前

- 不臆测：先读文件与调用方，弄清受影响的流程再改；不假设代码行为。
- 只做被要求的事：不顺手重构、不改无关格式、不做无关修复。范围之外的问题记录下来另行处理。

### 实现

- 决策阶梯，停在第一个能解决问题的选项：这个东西需要存在吗 → 复用仓库里已有实现 → 用标准库 → 用平台原生能力 → 用已安装依赖 → 一行能写清就写一行 → 否则写最小可运行实现。
- 优先删除而不是新增。用最少的文件、最小的 diff。
- 写无聊的代码，不写聪明的代码。避免多余抽象、单实现接口、投机性配置、为未来预留的脚手架。
- 修根因，不修症状；改共享行为前先看所有调用方，能修公共路径就修公共路径。
- 注释写「为什么」，不写「做了什么」；能靠命名说清的不写注释。

### 不可妥协

- 边界输入校验、防数据丢失的错误处理、安全控制、可访问性、关键边界 case 的正确性，任何简化都不能牺牲这些。
- **这个项目的核心不可妥协项**：分诊档必须有兜底、红旗判定不看模型、引用结论必须能核到原文、模型输出不得直接成为对外文案。改动这三处要单独起 PR 并说明。
- 密钥、token、个人配置不入库。健康相关数据一律不入测试夹具，测试用合成数据。
- 类型必须过 `mypy` 严格模式，不要用 `Any` 或 `# type: ignore` 逃逸；真需要忽略时写明原因。
- 非平凡的新逻辑必须留一个最小可运行检查：后端写成 pytest 测试，目录结构与命名镜像被测代码，断言具体输入输出而不是抽象桩数据。前端骨架期没有测试框架，改动以 `pnpm type-check`、`pnpm check:interactions` 加 `pnpm build:h5` 为准，引入测试框架要先在第 8 节登记再动手。

## 6. 后端与数据库须知

- 端口 8000，接口前缀 `/api` 只在 `app/main.py` 的 `include_router` 出现一次，**领域 router 里不写 `/api`**。
- 所有业务接口返回统一响应体：

```json
{ "code": 0, "message": "ok", "data": {} }
```

  `code == 0` 表示成功，非 0 是业务错误码，由 `app/common/codes.py` 的 `ErrorCode` 定义；前端只判断 `code`，不解析 `message`。HTTP 状态码仍然表达语义：400 参数错误、401 未认证、403 无权限、404 不存在、500 服务端异常。
- 分页统一 `data = { records, total, page, size }`（列表接口尚未落地，落地时按这个形状）。
- 时间统一 `Asia/Shanghai`，接口返回 `yyyy-MM-dd HH:mm:ss` 字符串。
- 健康检查是 `/api/health`，**不查库**。测试套件需要 Postgres：pytest 每个会话重建 `clear_complaint_test` 并跑 Alembic 迁移，本地先 `docker compose up -d`，CI 的 backend job 带 `services: postgres`。
- 业务错误抛 `BizException(ErrorCode.XXX, "可选的自定义消息")`，全局处理器会转成统一响应体。未匹配的路径与不支持的方法已经映射到对应错误码，不要让它们掉进兜底的 500 分支。
- 数据库访问用 SQLAlchemy 2.x async 加 asyncpg。会话通过 `Depends(get_session)` 注入，不要在路由里自己 `SessionLocal()`。模型继承 `app/db/base.py` 的 `Base`。
- **禁止代码建表**：不调用 `Base.metadata.create_all`，不写 `CREATE TABLE`。表结构只由 Alembic 迁移创建。
- 迁移：`uv run alembic revision -m "说明"` 生成脚本，版本号自动递增，已提交的迁移文件不改内容，要改就加新版本。新增模型后要 import 进 `alembic/env.py`，autogenerate 才看得到。
- 表名、字段名 `snake_case`；表名用单数（`episode`、`citation`）。主键 `BIGINT GENERATED BY DEFAULT AS IDENTITY`；时间字段 `created_at` / `updated_at`，`TIMESTAMPTZ NOT NULL DEFAULT now()`。
- 库名 `clear_complaint`，本地凭据 `clear_complaint` / `clear_complaint` 写在 `docker-compose.yml` 与 `.env.example` 里，仅限本地。生产走环境变量 `DATABASE_URL`，禁止把真实凭据提交进仓库。
- 依赖加进 `pyproject.toml` 的 `[project].dependencies`（运行时）或 `[dependency-groups].dev`（开发期），用 `uv add` 改，不要手写版本号。
- 调 AgentArts 平台时注意：调用接口是 SSE 事件流，必须带 `x-hw-agentarts-session-id`，且不能使用平台赠送的免费模型额度，否则返回 `Model call failed`。这部分客户端尚未接入（见第 8 节）。

## 7. 前端须知

- 底座是 uni-app 官方 `vite-ts` 模板。`@dcloudio/*`、`vite`、`typescript`、`vue-tsc` 的版本是模板锁定的组合，**不许单独升级其中任何一个**，要升就整体切换到新的模板版本。
- 只保留 H5 与微信小程序两个平台及其 `dev:` / `build:` 脚本。要加别的端（App、支付宝小程序等）先在 issue 里讨论，别顺手装回来。
- 小程序端不许出现 `window` / `document` / DOM API，分端差异用条件编译（`// #ifdef H5`、`// #ifdef MP-WEIXIN`）。布局单位优先 `rpx`，适配 PC 宽屏用 `@media` 断点。
- 请求只走 `src/request/`，页面里不直接调 `uni.request` 或 `axios`。H5 用相对路径 `/api`，由 Vite 代理转发到 8000，代码里不出现后端域名；小程序端没有代理，`request` 会退回 `VITE_API_BASE`，本地默认 `http://localhost:8000/api`，真机必须换成备案过的 HTTPS 域名。
- 状态用 Pinia，已在 `src/main.ts` 注册，store 放 `src/stores/`，跨页面状态都放这里。
- 样式先用普通 CSS。`uni.scss` 里的变量要装了 `sass` 才可用，等真需要嵌套或主题变量时再加这个依赖。暂不引入 UI 组件库与原子化 CSS（见第 8 节）。
- 条件编译注释在 `.ts` 里同样生效，但 `vue-tsc` 看到的是未处理的源码：不要用 `#ifdef` / `#ifndef` 两个分支各写一个同名 `const`，改成 `let` 加条件赋值，否则类型检查报重复声明。
- 微信小程序主包上限 2MB，图片走 CDN 或外链，页面多了用 `subPackages` 分包。小程序 appid 尚未申请，`manifest.json` 里留空。

## 8. 明确推迟的决定

下表是主动推迟的事项。要做其中任何一项，先改这张表，再动代码。

| 事项 | 现状 | 备注 |
| --- | --- | --- |
| 账号四表（V1、V2）、问诊四表（V3：`episode`/`episode_answer`/`idempotency_key`/`reminder`）、档案三表（V4：`vital`/`medication`/`medication_plan`） | 已建 | 表随域逐个补迁移，字段设计依 docs/api.md |
| AgentArts 客户端 | 已接入 | `app/agent/client.py` 传输层 + `app/episode/platform.py`、`app/reminder/platform.py` 打桩点；问诊生成、澄清、兜底（M4）与随访第二层（M6c）均已接真流。Triage 切到 RouteSafe 运行时 `2026-11-26.mainflow-io.6`，`request.v2`/`workflow.v2`（原文进、理解出）：单问协议由后端赋号、10/5 双周期计数、结果修订带 cap 3 回看、out_of_coverage 单向阀、危机命中在任何平台调用之前短路、#25 档案上下文随每次请求；v1 预提取与 io.5 时代的补丁逻辑全部删除。Profile 与 Followup 运行时版本保持 `.2`，代码中的请求 `schema_version` 字面量为 `clear-complaint.profile-intake.request.v1` 与 `clear-complaint.followup-supplement.request.v1`。io.6 运行时 Key 已于 2026-11-26 通过 HTTP 鉴权（见 #23）；22 景回归用例包同日执行（17/23 通过，4 败为平台侧问题，见 #31），Issue31Fix 运行时（验收值 `2026-11-26.mainflow-io.6.issue31.1`）复测 14/14 零 4004。#31 待平台澄清两点后关闭。受限问答与约束详情端点未做 |
| 每日健康关怀（Daily-Health-Companion 工作流） | 规划中 | 契约见私有交接文档 16.8；发布 URL 已于 2026-11-24 实测通过（四个验收用例加两个负向）。计划在 docs/daily-companion.md：D0 只做登记，D1–D3 为后端（Settings、client 映射、`app/daily` 领域包、`daily_report` 迁移），D4 为前端展示页，D5 推迟真实设备适配、定时生成与推送。密钥已在交接截图中明文出现，正式启用前先轮换 |
| 归一化、红旗短路、引用核验、受控词表与科室表 | 已写（M5） | `app/agent/normalize.py、redflag.py、citation.py、vocab.py、departments.py` + `data/` 三张冻结表（版本 1），复制自 experiment 并独立维护；测试断言取自 handoff/constraints.md。已知边界：否定 6 字窗口会盖住紧随其后的第二个真命中 |
| 登录鉴权 | 已做（账号域） | HS256 访问令牌 2h、刷新令牌 30 天轮换（重放 1005）；注册/登录/刷新/登出已上线，其他域按需接 `get_current_user` |
| 小程序 appid | 未申请 | 真机调试前必须补 |
| 测试数据库 | 已接 | `tests/conftest.py` 每个会话重建 `clear_complaint_test`（环境变量 `TEST_DATABASE_URL`，默认 `localhost:5432`）并执行 `alembic upgrade head`；CI 的 backend job 带 `services: postgres` |
| Redis | 未接入 | 先不加依赖 |
| 病历上传 / OCR | 未做 | 后端无接口，界面标记已移除；等上面的对象存储行定案后再做，不做模拟导入 |
| 问诊侧增强（约束详情、纠偏评分、前后效果对比） | 未做 | 连续追问已随 request.v2 在 #29 落地：结果后输入沿用同一问诊、结果按修订演进并保留回看。其余三项仍在路线图，逐项单独落地，不塞模拟数据 |
| 对象存储（图片上传） | 未选型 | 等真有上传需求 |
| 接口文档与前端类型生成 | 未接入 | FastAPI 自带 OpenAPI，`openapi-typescript` 是候选方案 |
| UI 组件库、UnoCSS、`sass` | 未引入 | 样式用普通 CSS |
| 前端测试框架 | 未引入 | 用两个 Node 脚本代替：`pnpm check:interactions`（离线，进 CI）、`pnpm check:live`（手动，对本机服务联调）。仍以 `pnpm type-check`、`pnpm build:h5` 与手测为准 |
| 应用容器化部署 | 推迟 | 开发期应用不进容器；等有服务器再补 `backend/Dockerfile` 与 `docker-compose.prod.yml`（nginx 托管 `frontend/dist`） |
