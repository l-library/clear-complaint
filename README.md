# 清诉 ClearComplaint

> 面向个人的健康管理智能体：把一段模糊的自然语言主诉，变成一份可核验、能递给医生的分诊结论。

用户说"我最近常常流鼻涕"，系统给出该不该就诊（急诊、门诊、一周内复观察）、挂什么科、可能相关的几种常见情况（每条带引用原文），以及就诊前该准备什么。所有结论都标着"不构成诊断"。

项目同时是一项实验研究的工程化产物。研究的问题是这个场景下模型对表述形式的敏感性：同一段临床意图换成不同说法，结论会不会漂移，以及把用户的自我诊断暗示从推理链里摘出去之后能压回来多少。研究结论直接成为产品里的一组约束，不是附录里的调研。

## 功能

### 分诊建议

自然语言描述症状，系统给出分诊档与首推科室。红旗症状（胸痛伴出汗、意识改变、持续高热、呼吸困难等）由确定性规则短路到急诊，不看模型输出。

### 带引用的可能情况

给出 3 到 5 条可能相关的常见情况，每条都能核到指南原文的片段。引用只能从本轮检索结果里选，核不上就删掉这一条。

### 澄清与追问

关键字段（起病时间、持续时长、部位、性质、伴随症状）缺失时先追问，不急着下结论。

### 健康档案

结构化记录症状、分诊结论、就诊结果和用药计划。模型生成的摘要不落库，避免把自己的幻觉当病历存下来。

### 随访与提醒

分诊档为"自我观察"的，48 到 72 小时后主动追问，未缓解则升级建议。用药提醒由用户自己录入的计划驱动，助手只负责措辞和追问。

## 技术栈

| 部分 | 选型 |
| --- | --- |
| 前端 | uni-app（Vue 3 + Vite + TypeScript），一套代码编译到 H5 与微信小程序 |
| 后端 | Python 3.14 + FastAPI，uv 管理依赖与虚拟环境 |
| 持久层 | SQLAlchemy 2.x（async）+ asyncpg，迁移用 Alembic |
| 数据库 | Postgres 16（本地跑在 Docker 里） |
| 智能体编排 | 华为云 AgentArts（低代码工作流与多智能体，在平台侧配置） |
| 质量门禁 | ruff、mypy 严格模式、pytest |

## 本地运行

需要 uv、Node + pnpm、Docker。

```bash
docker compose up -d                          # Postgres，端口 5432
cd backend && uv sync                         # 准备虚拟环境与依赖
cp .env.example .env                          # 本地配置
cd backend && uv run alembic upgrade head      # 迁移（当前没有迁移脚本）
cd backend && uv run uvicorn app.main:app --reload   # 后端 8000，接口前缀 /api
cd frontend && pnpm install
cd frontend && pnpm dev:h5                    # 浏览器 http://localhost:5173
```

健康检查：`curl http://localhost:8000/api/health`。

小程序端用 `cd frontend && pnpm dev:mp-weixin` 出产物，再用微信开发者工具打开 `frontend/dist/dev/mp-weixin`。

提交前：后端 `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`，前端 `pnpm type-check && pnpm build:h5`。

## 当前进度

前端已经完成桌面优先的交互预览，包括登录注册、档案完善、连续问诊、动态追问、分诊草稿、结果详情、健康档案、血压趋势、用药管理、提醒随访和数据账户页面。界面使用 Hallmark 的 Dose 方案重做，同时提供手机端响应式布局和免登录交互预览模式。

前端已经封装登录、档案、问诊 SSE、结果、血压、用药、提醒和数据管理请求，并处理 Bearer Token、刷新、登录态守卫、流式中断恢复和错误重试。Hallmark 渲染审查为 `0 FAIL / 0 REFLEX / 0 WARN`，`pnpm type-check` 与 `pnpm build:h5` 均通过。

当前分支中的后端仍只有统一响应、错误码、全局异常处理、`/ping`、`/health`、数据库会话和 Alembic 目录。真实后端和 AgentArts 的最终联调仍需在对应后端分支与实际服务环境中完成。

界面截图、启动方式和联调所需材料见 [前端预览与联调说明](docs/前端预览与联调说明.md)，完整页面与功能范围见 [前端功能与页面清单](docs/前端功能与页面清单.md)。

计划、实验设计与风险清单见 [docs/PLAN.md](docs/PLAN.md)，赛题规则与平台限制见 [docs/赛题调研.md](docs/赛题调研.md)。

目录结构、开发环境、Git 与编码约定见 [CONVENTION.md](CONVENTION.md)（中文）及其英文镜像 [AGENTS.md](AGENTS.md)。
