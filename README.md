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

随访与复查提醒关联已保存的问诊，从健康计划进入统一 AI 对话。用药计划根据本人已确认的医嘱录入，计划与打卡持久化到后端；尚不发送系统通知。

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

Windows 本机已有依赖和 `backend/.env` 时，可在项目根目录运行 `./start-local.ps1`。脚本保留现有数据库数据，检查并启动 Docker、Postgres、后端及 H5 开发服务，检查就绪后输出 `http://127.0.0.1:5175/`。日志位于被 Git 忽略的 `.tools/runtime/`；电脑重启或注销后需要重新启动应用服务。

```bash
docker compose up -d                          # Postgres，端口 5432
cd backend && uv sync                         # 准备虚拟环境与依赖
cp .env.example .env                          # 本地配置
cd backend && uv run alembic upgrade head      # 执行迁移
cd backend && uv run uvicorn app.main:app --reload   # 后端 8000，接口前缀 /api
cd frontend && pnpm install
cd frontend && pnpm dev:h5                    # 浏览器 http://localhost:5173
```

健康检查：`curl http://localhost:8000/api/health`。

小程序端用 `cd frontend && pnpm dev:mp-weixin` 出产物，再用微信开发者工具打开 `frontend/dist/dev/mp-weixin`。

提交前：后端 `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`，前端 `pnpm type-check && pnpm build:h5`。

## 当前进度

前端保留统一的中文对话首页、左侧导航及玻璃信息面板，使用真实 `/api` 请求接入账户与隐私授权、个人档案、SSE 问诊、问诊历史、体征、用药记录、用药计划、提醒响应和数据导出。问诊与随访共用聊天入口；接口失败显示错误，不回退到模拟数据。旧版演示代码已清理。

后端已包含账户、问诊、档案、提醒、六个 Alembic 迁移和 AgentArts 客户端。平台凭据只写入被 Git 忽略的 `backend/.env`；工作流不可用时返回明确标记的保守兜底结果。OCR、文件上传、独立档案采集路由、结果后问答和系统通知尚未实现。

真实本机联调：先启动数据库、后端和 H5 开发服务，再在 `frontend/` 执行 `pnpm check:live`。默认通过 `http://127.0.0.1:5175` 验证前端请求与 Pinia 状态；其他本机端口可用 `LIVE_APP_ORIGIN` 指定。脚本仅使用临时合成账号，结束时删除该账号，不写入真实健康资料；运行报告保存在 `output/live-api-check.json`。类型与离线交互校验仍使用 `pnpm type-check`、`pnpm check:interactions`。

计划、实验设计与风险清单见 [docs/PLAN.md](docs/PLAN.md)，赛题规则与平台限制见 [docs/赛题调研.md](docs/赛题调研.md)。

目录结构、开发环境、Git 与编码约定见 [CONVENTION.md](CONVENTION.md)（中文）及其英文镜像 [AGENTS.md](AGENTS.md)。
