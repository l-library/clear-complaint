# 清诉前端工作区

当前工作区使用真实 `/api` 请求，接口契约以 `docs/api.md` 为准。旧版本地模拟状态、组件、类型和配套检查已删除。

## 页面与入口

| 页面 | 路由 | 可选参数 |
| --- | --- | --- |
| 首页 | `/pages/index/index` | 无 |
| AI 对话 | `/pages/chat/index` | `conversation_id`；随访使用 `reminder_id` 和 `date` |
| 健康档案 | `/pages/health-records/index` | 无 |
| 健康计划 | `/pages/health-plans/index` | `tab=all`、`tab=follow_up` 或 `tab=medication` |

H5 默认使用 hash 路由，例如 `/#/pages/health-plans/index`。页面共用 `QWorkspace.vue`，桌面保留左侧导航、聊天和右侧账户面板；手机使用底部导航，最近问诊从顶部时钟按钮打开。

## 实现与数据来源

- `stores/liveWorkspace.ts` 管理问诊、澄清、归档、历史记录和随访状态；`stores/auth.ts` 管理登录、刷新和退出。
- `QLiveArchive.vue` 展示服务器返回的档案、问诊、体征和用药记录；`QLivePlans.vue` 管理服务器用药计划和提醒响应。
- `QAccountPanel.vue` 接入账户、隐私授权、个人档案和数据导出；`QConsultationFlow.vue` 展示问诊与随访的实际服务响应。
- 所有请求通过 `src/api/` 和 `src/request/`。H5 使用相对路径 `/api`，由开发服务器代理到后端；小程序使用 `VITE_API_BASE`。
- 问诊通过 SSE 接收进度并读取最终结果；重试沿用幂等键，退出登录后丢弃迟到的会话响应。接口失败显示错误，不生成模拟回复或替代记录。
- 随访从健康计划进入共用聊天页；普通问诊历史只展示后端问诊列表。病历导入与 OCR 尚未接入。

## 检查

提交前运行 `pnpm type-check`、`pnpm check:interactions`、`pnpm build:h5` 和 `pnpm build:mp-weixin`。

`pnpm check:interactions` 检查请求鉴权、令牌刷新、SSE 解析、发送消息过渡、重试和退出登录隔离，使用合成数据，不新增测试框架。

本机服务启动后可运行 `pnpm check:live`，使用独立合成账户联调真实接口并清理账户；报告位于被 Git 忽略的 `output/`。启动方式见根目录 README 和 `start-local.ps1`。
