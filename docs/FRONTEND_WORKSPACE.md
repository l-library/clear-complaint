# 清诉前端工作区

当前工作区使用真实 `/api` 请求，接口契约以 `docs/api.md` 为准。旧版本地模拟状态、组件、类型和配套检查已删除。

## 页面与入口

| 页面 | 路由 | 可选参数 |
| --- | --- | --- |
| 默认入口（跳转到 AI 对话） | `/pages/index/index` | 无 |
| AI 对话 | `/pages/chat/index` | `conversation_id`；随访使用 `reminder_id` 和 `date` |
| 健康档案 | `/pages/health-records/index` | 无 |
| 健康计划 | `/pages/health-plans/index` | `tab=all`、`tab=follow_up` 或 `tab=medication` |

H5 默认使用 hash 路由，例如 `/#/pages/health-plans/index`。页面共用 `QWorkspace.vue`，桌面保留左侧导航、聊天和右侧账户面板；手机使用底部导航，最近问诊从顶部时钟按钮打开。

入口统一为中文对话首页，原英文落地页及专用状态、样式已移除。隐私与敏感信息说明使用 `/pages/privacy/index?section=privacy|sensitive` 站内页面，服务主体和联系方式待补充。

档案草稿由 `stores/profileDraft.ts` 在当前登录会话的内存中保留，关闭弹窗或保存失败不会清空，退出或切换账户时清除；不写入本机持久化存储。未选择城市时成对提交 `null`，不会触发行政区码校验。城市选择数据冻结自 [Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China) 的 `pc-code.json`，直辖市合并到市级；名称和代码一起提交。

健康计划默认查询今天起连续 7 天的真实提醒并排序，不生成虚构提醒；可选择其他起始日。档案概览提供身高与体重的直接录入按钮。

## 实现与数据来源

- `stores/liveWorkspace.ts` 管理问诊、澄清、归档、历史记录和随访状态；`stores/auth.ts` 管理登录、刷新和退出。
- `QLiveArchive.vue` 展示服务器返回的档案、问诊、体征和用药记录；`QLivePlans.vue` 管理服务器用药计划和提醒响应。
- `QAccountPanel.vue` 接入账户、隐私授权、个人档案和数据导出；`QConsultationFlow.vue` 展示问诊与随访的实际服务响应。
- 所有请求通过 `src/api/` 和 `src/request/`。H5 使用相对路径 `/api`，由开发服务器代理到后端；小程序使用 `VITE_API_BASE`。
- 问诊通过 SSE 接收进度并读取最终结果；重试沿用幂等键，退出登录后丢弃迟到的会话响应。接口失败显示错误，不生成模拟回复或替代记录。
- 随访从健康计划进入共用聊天页；普通问诊历史只展示后端问诊列表。病历导入与 OCR 尚未接入。

## 细节能力

- 聊天右侧保留玻璃面板，提供“纠偏与评估”和“账户信息”两个页签。前者展示问诊详情返回的原文、整理信息、单独记录的原因推测，以及红旗和引用校验记录，不计算额外分数。
- 健康档案支持问诊状态与就医建议、体征类型、用药类型与状态筛选。筛选使用后端查询参数，分页沿用当前筛选条件，不影响侧栏最近问诊。
- 趋势支持近 7、30、90、180、365 天和每类最多 10、20、50 条记录；没有记录时显示空状态。
- 已停用的用药记录可以恢复为当前记录，原先暂停的提醒计划不会自动恢复。
- 非急诊问诊归档后仍可补建提醒。就诊提醒的日期范围遵循原问诊创建日后 3–14 天，已有待处理提醒保留原时间。
- 随访返回准备事项索引时提供原问诊记录入口。现有提醒接口没有原问诊编号，因此不猜测关联清单内容；后端和接口契约保持不变。
- 病历上传／OCR、独立约束详情、纠偏评分与前后效果对比保留待接入说明，不显示模拟结果。结果后的连续追问已随单问协议落地：完成后输入沿用同一问诊并按修订更新结果。

## 检查

提交前运行 `pnpm type-check`、`pnpm check:interactions`、`pnpm build:h5` 和 `pnpm build:mp-weixin`。

`pnpm check:interactions` 检查请求鉴权、令牌刷新、SSE 解析、发送消息过渡、重试和退出登录隔离，使用合成数据，不新增测试框架。

本机服务启动后可运行 `pnpm check:live`，使用独立合成账户联调真实接口并清理账户；报告位于被 Git 忽略的 `output/`。启动方式见根目录 README 和 `start-local.ps1`。
