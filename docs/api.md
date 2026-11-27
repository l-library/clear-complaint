# 清诉 API

本文定义清诉后端的对外接口，是前端 `src/api/` 与后端 `app/<domain>/` 的实现依据。产品行为、页面结构与状态机的完整描述见《清诉主流程》；本文只负责 HTTP 契约。

> 后端调用 AgentArts 工作流的内部契约（运行时地址、请求封装、字段映射、超时与降级）已拆分至 [api-agentarts.md](api-agentarts.md)，本文件只保留前后端契约；接口定义不等于功能已实现。


## 1. 范围与约定

### 1.1 基础信息

| 项 | 值 |
| --- | --- |
| 基础路径 | `/api`，前缀只在 `app/main.py` 的 `include_router` 出现一次 |
| 传输 | HTTPS；本地开发为 `http://localhost:8000/api` |
| 编码 | 请求与响应均为 `application/json; charset=utf-8`；流式接口为 `text/event-stream` |
| 字段命名 | `snake_case` |
| 版本 | 当前无版本号，路径不带 `v1`；破坏性变更时再引入 |
| 接口文档 | FastAPI 自带 `/docs` 与 `/openapi.json`，仅开发环境开放 |

### 1.2 响应包

所有非流式接口返回统一包体：

```json
{ "code": 0, "message": "ok", "data": {} }
```

- `code == 0` 为成功，`data` 承载业务数据。
- `code != 0` 为业务错误，`data` 为 `null`，`message` 为可直接展示的中文文案（前端仍按 `code` 取自己的文案表，`message` 只用于日志与排查）。
- HTTP 状态码同时表达语义：400 参数问题、401 未认证、403 无权限、404 不存在、409 状态冲突、429 频率限制、500 服务异常、502/503/504 平台侧问题。
- 错误码 `code` 使用第 12 节的号段，与 HTTP 状态码可以不同值。

### 1.3 时间、日期与单位

| 类型 | 格式 | 示例 |
| --- | --- | --- |
| 时间戳 | `yyyy-MM-dd HH:mm:ss`，`Asia/Shanghai` | `2026-12-01 09:30:00` |
| 日期 | `yyyy-MM-dd` | `2026-12-01` |
| 时刻 | `HH:mm` | `08:00` |
| 单位 | cm、kg、mmHg、次/分 | — |

服务端负责格式化，前端不拼接、不换算时区。

### 1.4 分页

查询参数 `page`（从 1 开始，默认 1）与 `size`（默认 20，最大 100）。列表响应统一为：

```json
{ "records": [], "total": 0, "page": 1, "size": 20 }
```

### 1.5 鉴权

- 除 `/api/ping`、`/api/health`、`/api/auth/register`、`/api/auth/login`、`/api/auth/refresh` 外，所有接口都要求 `Authorization: Bearer <access_token>`。
- 访问令牌 2 小时有效，刷新令牌 30 天有效并轮换。刷新接口成功即返回新的一对令牌，旧刷新令牌作废；重放旧令牌返回 1005。
- 允许多端同时在线，不做单点踢出。
- 未携带令牌或令牌无法解析返回 401 + 401；访问令牌过期返回 401 + 1004；密码错误返回 401 + 1003。三者状态码相同，`code` 不同。

### 1.6 幂等

- `POST /api/episodes`、`POST /api/episodes/{id}/retry`、`POST /api/episodes/{id}/clarify`、`POST /api/episodes/{id}/skip-clarify` 需要请求头 `Idempotency-Key`（UUID v4，长度 36）。
- 同一个键 30 分钟内只处理一次：重复请求返回同一次问诊并附着到进行中的流；若该问诊已生成完毕，直接返回整包事件。
- 同一个键携带不同请求体返回 409 + 2006。
- 缺少该请求头按参数错误处理，返回 400 + 400。

### 1.7 枚举

| 名称 | 取值 |
| --- | --- |
| 分诊档 `triage` | `emergency` 急诊 / `clinic` 门诊 / `self_observe` 自我观察 |
| 科室 `department` | 急诊科、呼吸内科、消化内科、心血管内科、神经内科、感染科、皮肤科、儿科、全科医学科、肾内科、内分泌科、眼科、普通外科、骨科、急诊外科、肿瘤科、精神心理科（共 17 个，来自 `experiment/corpus/departments.json`） |
| 性别 `sex` | `male` / `female` / `undisclosed` |
| 问诊状态 `episode.status` | `clarifying` / `generating` / `saved` / `failed` / `expired`（v2 完成即归档，`ready` 不再是持久状态） |
| 体征类型 `vital.kind` | `height` / `weight` / `bp` |
| 用药类型 `medication.kind` | `long_term` / `short_term` |
| 用药状态 `medication.status` | `active` / `stopped` / `expired` |
| 提醒类型 `reminder.kind` | `followup` / `recheck` / `medication` |
| 提醒状态 `reminder.status` | `pending` / `done` / `skipped` / `missed` / `expired` |

分诊档与科室是受控值，前端不硬编码文案以外的判断逻辑；科室中文名直接作为展示文案。

## 2. 数据对象

以下对象在多处复用，后文只引用名称。

### 2.1 TokenPair

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "9f2b7c...",
  "token_type": "Bearer",
  "access_expires_at": "2026-12-01 11:30:00",
  "refresh_expires_at": "2026-12-31 09:30:00"
}
```

### 2.2 User

```json
{ "id": 1024, "phone": "13800138000", "is_demo": false, "created_at": "2026-11-20 10:00:00" }
```

### 2.3 Profile

```json
{
  "name": "张三",
  "birth_date": "1990-06-12",
  "age_years": 36,
  "sex": "male",
  "city_code": "310100",
  "city_name": "上海市",
  "conditions": ["高血压"],
  "condition_note": "2019 年确诊，规律服药",
  "allergies": ["青霉素"],
  "allergy_note": null,
  "required_missing": [],
  "updated_at": "2026-11-25 20:10:00"
}
```

`age_years` 由 `birth_date` 计算，前端不传。`required_missing` 列出缺失的必填项（`birth_date`、`sex`），为空表示可以提交主诉。

### 2.4 Vital

```json
{
  "id": 11,
  "kind": "bp",
  "measured_at": "2026-11-28 08:10:00",
  "height_cm": null,
  "weight_kg": null,
  "systolic": 128,
  "diastolic": 82,
  "pulse": 72,
  "created_at": "2026-11-28 08:12:00"
}
```

按 `kind` 取用对应字段：`height` 只用 `height_cm`，`weight` 只用 `weight_kg`，`bp` 用 `systolic`、`diastolic`、`pulse`。其他字段为 `null`。

### 2.5 Medication

```json
{
  "id": 5,
  "name": "氨氯地平",
  "dosage_text": "1 片",
  "frequency_text": "一天一次",
  "kind": "long_term",
  "started_on": "2025-03-01",
  "ended_on": null,
  "status": "active",
  "created_at": "2026-11-20 10:05:00"
}
```

### 2.6 MedicationPlan

```json
{
  "id": 3,
  "medication_id": 5,
  "times": ["08:00"],
  "started_on": "2026-11-20",
  "ended_on": "2026-12-20",
  "status": "active",
  "note": "饭后吃",
  "created_at": "2026-11-20 10:06:00"
}
```

### 2.7 Evidence 与 Condition

```json
{
  "name": "急性上呼吸道感染",
  "evidence": [
    { "doc_title": "普通感冒规范诊治的专家共识", "section": "临床表现", "quote": "以鼻塞、流涕、喷嚏、咽痛为主要表现，全身症状较轻。" }
  ]
}
```

`quote` 为逐字摘录，先对照原分片核验，再截取最多 120 字符；内部保留截断标记，省略号只在展示时追加，不写入待核验的摘录。`evidence` 至少一条，核验不通过的情况不会出现在结果里。平台到后端的转换见《[api-agentarts.md](api-agentarts.md)》16.3 节。

### 2.8 Result

```json
{
  "triage": "clinic",
  "triage_label": "门诊",
  "urgency_note": "建议数日内就诊，症状加重时提前",
  "department_primary": "呼吸内科",
  "department_secondary": "全科医学科",
  "conditions": [],
  "prep": {
    "bring": ["医保卡与既往检查报告", "正在服用的药物清单"],
    "describe": ["症状从什么时候开始", "鼻塞与流涕的先后顺序"],
    "go_now": ["出现呼吸困难或高热不退时立即前往急诊"]
  },
  "disclaimer": "清诉不构成诊断，最终判断以医生为准。"
}
```

`department_secondary` 可为 `null`。`conditions` 在全部核验失败时为空数组，此时 `degraded` 不一定为真（见 5.6）。

### 2.9 Gate（确定性动作摘要）

```json
{
  "red_flags": [{ "rule_id": "RF12", "name": "胸痛持续不缓解伴大汗" }],
  "citations_verified": 4,
  "citations_dropped": 1,
  "clarify_rounds": 0,
  "degraded": false,
  "fallback": false
}
```

### 2.10 EpisodeSummary

```json
{
  "id": 9001,
  "status": "saved",
  "created_at": "2026-11-30 21:14:00",
  "saved_at": "2026-11-30 21:15:10",
  "complaint_excerpt": "这两天一直流鼻涕，嗓子有点干",
  "triage": "self_observe",
  "triage_label": "自我观察",
  "department_primary": "呼吸内科",
  "degraded": false
}
```

### 2.11 EpisodeDetail

```json
{
  "episode": {
    "id": 9001,
    "status": "clarifying",
    "created_at": "2026-11-30 21:14:00",
    "saved_at": null,
    "expires_at": "2026-12-30 21:14:00",
    "complaint_text": "这两天一直流鼻涕，嗓子有点干",
    "revision": 0
  },
  "normalized": {
    "symptom": ["流鼻涕", "咽干"],
    "onset_at": "两天前",
    "duration_text": "2 天",
    "site": ["鼻", "咽"],
    "nature": "清水样",
    "associated": [],
    "medications_text": "没吃药"
  },
  "self_attribution": "可能是着凉了",
  "env": { "city_code": "310100", "city_name": "上海市", "weather": null, "fetched_at": "2026-11-30 21:14:02" },
  "clarify": {
    "asked_count": 1,
    "limit": 10,
    "skipped": false,
    "pending": {
      "question_id": "q1",
      "purpose": "duration",
      "text": "这次不舒服持续多久了？",
      "can_skip": true
    }
  },
  "result": {},
  "result_history": [],
  "gate": {},
  "qa_turns": [],
  "profile_snapshot": {},
  "vitals_snapshot": {},
  "disclaimer": "清诉不构成诊断，最终判断以医生为准。"
}
```

- `clarify` 在 `status=clarifying` 时为待答单问对象（结构见 2.12），否则为 `null`。
- `result` 在 `saved` 时存在；`result_history` 是被修订取代的旧版本（最近三版），`episode.revision` 为当前修订号（首版结果即 1）。
- `normalized` 与 `self_attribution` 是工作流理解输出的回填：`symptom` 为列表，其余为文本或 `null`；不再有后端预提取。
- `profile_snapshot` 与 `vitals_snapshot` 是生成时的事实快照，之后修改档案不影响它。
- `env` 在取不到环境信息时为 `null`。
- `qa_turns` 为该问诊的受限问答记录，按时间正序，结构见 2.14；只读。

### 2.12 单问协议与回答（io.6 / request.v2）

问诊的补问改为一次一问，一条回答可以同时补充多项信息；理解归工作流，后端只管台账、计数与复核。

`POST /api/episodes/{id}/clarify` 每次提交一条回答原文：

```json
{ "question_id": "q1", "action": "answer", "text": "三天了，主要是上腹部疼，没吃过药" }
```

| 字段 | 规则 |
| --- | --- |
| `question_id` | 必须对上当前待答问题；结果后的主动补充传 `null` |
| `action` | `answer` / `unknown` / `skip`；`unknown` 与 `skip` 不转成「没有」，原文可空 |
| `text` | 回答原文，不改写不折算，最多 500 字；`answer` 不允许空 |

SSE `question` 事件（详情 `clarify.pending` 同构）：

```json
{
  "episode_id": 12,
  "question_id": "q1",
  "purpose": "duration",
  "text": "这次不舒服持续多久了？",
  "can_skip": true,
  "not_understood": false
}
```

- `question_id` 由后端赋号、episode 内稳定；重复收到同一编号不重复展示、不重复计数
- `purpose` 取值 `onset / duration / location / character / associated_symptoms / medication / other`
- 提问按唯一问题计数：网络重试与重复事件不计数，一条回答补多项不加问数；`unknown` 与 `skip` 计入上限
- 初始生成周期上限 10 问，每个结果修订周期 5 问；到上限不硬停，工作流按现有信息收尾
- `POST /api/episodes/{id}/skip-clarify` 表示整体停止补问，与单题 `action=skip` 不同

**修订**：结果生成后继续补充（`question_id=null`）沿用同一 `episode_id`，结果按修订版本演进——`episode.revision` 首版为 0，每接受一版 +1；被取代的旧结果保留在 `result_history`（最近三版）供回看。`saved_at` 不随修订重置，提醒按 episode 与 pending 状态去重，幂等指纹包含本次原话，迟到旧结果按 `base_revision` 拒收。

**状态与出口**（工作流 status → 用户可见）：

| 出口 | 表现 |
| --- | --- |
| 完整版 | 现有分诊卡 + 引用核验，不变 |
| 覆盖范围版 | `gate.out_of_coverage=true`、`notice` 事件带边界声明、`conditions` 整节空；`self_observe` 一律抬到 `clinic`，`emergency` 保留 |
| 没听懂 | `not_understood=true` 时 `question` 事件为温和澄清；无问可发时 `notice` 事件温和结束，不吐分诊模板 |
| 空检索 / 平台故障 | 兜底 + `degraded` 标记（io.5 语义不变），`gate.retrieval` 带检索诊断 |
| 危机文本 | `safety` 事件带固定应对与求助渠道，无分诊段落；后端确定性识别、不调工作流 |

`normalized` 是理解输出的回填（展示用），不再是请求输入；平台契约与字段差异见 `api-agentarts.md` 16.3-v2。

### 2.13 随访补充清单（Supplement）

```json
{
  "watch_for": ["夜里是否咳醒", "体温是否继续升高"],
  "prepare_idx": [0, 2],
  "next_question": "这两天夜里睡得怎么样？"
}
```

- `watch_for` 每项取自受控症状词表，只描述可观察的表现，不含处置。
- `prepare_idx` 是该问诊 `result.prep` 候选清单的下标，服务端按原顺序展开成文本，越界或重复的下标被丢弃。
- 第二层未生成、超时或校验不通过时整个 `supplement` 为 `null`，降级标记记在随访记录上，不出现在响应对象里。

### 2.14 受限问答记录（QaTurn）

```json
{
  "id": 31,
  "question": "为什么建议门诊而不是观察",
  "intent": "evidence",
  "answer": {
    "basis": [
      { "doc_title": "普通感冒规范诊治的专家共识", "section": "临床表现", "quote": "以鼻塞、流涕、喷嚏、咽痛为主要表现，全身症状较轻。" }
    ],
    "relation_text": "你描述的是两天清水样鼻涕伴咽干，没有红旗表现。",
    "next_text": "症状超过一周不缓解，或出现发热、气促，再去门诊复评。"
  },
  "red_flag": null,
  "created_at": "2026-11-30 21:16:02"
}
```

- `intent` 取值：`evidence`、`recap`、`next_steps`、`out_of_scope`、`red_flag`。
- `out_of_scope` 时 `answer.basis` 为空数组，`relation_text` 为固定文案，`next_text` 提示重新描述。
- `red_flag` 时 `answer` 为 `null`，`red_flag` 给出命中的规则（见 5.10）。
- `basis` 的条目只能来自该问诊已核验的引用，不重新检索。

## 3. 系统端点

### 3.1 `GET /api/ping`

连通性检查，无需鉴权。

```json
{ "code": 0, "message": "ok", "data": { "status": "up" } }
```

### 3.2 `GET /api/health`

健康检查，无需鉴权，不访问数据库。

```json
{ "code": 0, "message": "ok", "data": { "status": "up", "service": "clear-complaint-backend" } }
```

### 3.3 `GET /api/meta/privacy`

返回当前隐私政策版本与链接，无需鉴权。注册前用它取 `consent_version`。默认使用随前端交付的站内隐私说明地址，部署时可通过环境变量覆盖。显式配置为空表示尚未提供政策页面，前端应隐藏对应入口，不得展示占位地址。

```json
{ "current_version": "2026-11-01", "policy_url": "/#/pages/privacy/index?section=privacy", "sensitive_policy_url": "/#/pages/privacy/index?section=sensitive" }
```

## 4. 认证

### 4.1 `POST /api/auth/register`

注册并登录。无需鉴权。

请求：

```json
{
  "phone": "13800138000",
  "password": "abc12345",
  "consent_version": "2026-11-01",
  "accept_privacy": true,
  "accept_sensitive": true
}
```

| 字段 | 规则 |
| --- | --- |
| `phone` | 11 位数字，全局唯一 |
| `password` | 8–32 位，同时含字母与数字 |
| `consent_version` | 当前隐私政策版本，取自 `GET /api/meta/privacy` 的 `current_version` |
| `accept_privacy` / `accept_sensitive` | 必须同时为 `true`，否则 1006 |

响应 `data`：

```json
{ "user": {"id": 1024, "phone": "13800138000", "is_demo": false, "created_at": "2026-11-20 10:00:00"}, "tokens": {"access_token": "...", "refresh_token": "...", "token_type": "Bearer", "access_expires_at": "2026-11-20 12:00:00", "refresh_expires_at": "2026-12-20 10:00:00"}, "profile_complete": false }
```

`user` 与 `tokens` 的结构见 2.1、2.2。`profile_complete` 为 `false` 时前端跳档案初始化页。

错误：1001 格式不合规、1002 手机号已注册、1006 未同意。

### 4.2 `POST /api/auth/login`

请求 `{ "phone": "13800138000", "password": "abc12345" }`，响应同注册。

错误：1003 账号或密码错误、1008 尝试次数过多（429，10 分钟内 5 次失败即锁定）。

### 4.3 `POST /api/auth/refresh`

请求 `{ "refresh_token": "..." }`，响应 `{ "tokens": {} }`。

错误：1005 刷新令牌无效或已被使用。

### 4.4 `POST /api/auth/logout`

请求 `{ "refresh_token": "..." }`，响应 `data: null`。该刷新令牌立即失效；其他端的登录态不受影响。

## 5. 问诊

### 5.1 `POST /api/episodes` 创建问诊（流式）

| 项 | 值 |
| --- | --- |
| 鉴权 | 必须 |
| 请求头 | `Idempotency-Key: <uuid>` |
| 请求体 | `{ "complaint": "...", "city_code": "310100" }` |
| 响应 | `text/event-stream`，事件见 5.11 |

`complaint` 去掉首尾空白后长度 1–500。`city_code` 可选，缺省使用档案常驻城市。

错误（在建立流之前以普通 JSON 信封返回）：2001 主诉为空、2002 超长、3001 档案必填项缺失、2006 幂等键冲突。

服务端顺序执行：落记录 → 归一化 → 红旗判定 → 取环境信息 → 写档案与体征快照 → 澄清或生成。命中红旗时跳过澄清追问，直接进入生成。

### 5.2 `POST /api/episodes/{id}/clarify` 提交追问回答（流式）

请求头同上，请求体：

```json
{
  "answers": [
    { "field": "duration_text", "value": "3 天" },
    { "field": "nature", "value": "不确定", "is_unknown": true }
  ]
}
```

- `answers` 长度 1–5，`value` ≤200 字，`field` 必须是本轮下发的字段，否则 2007。
- `is_unknown=true` 表示"不确定"或"跳过"，落库为未提供，不再追问。
- 响应为流：可能继续下发下一轮 `question` 事件，也可能直接进入生成并下发 `stage` 与 `result_section`。
- 错误：2005 当前状态不是 `clarifying`、2003 已到轮次上限（此时前端应改调 `skip-clarify` 或直接等待结果）。

### 5.3 `POST /api/episodes/{id}/skip-clarify` 跳过追问（流式）

无请求体，请求头同上。立即以现有字段生成结果，结果页标注信息不完整。错误：2005。

### 5.4 `POST /api/episodes/{id}/retry` 重新生成（流式）

仅 `failed` 状态可用，请求头同上，无请求体。复用原主诉与归一化字段，不新建问诊。错误：2005。

### 5.5 `GET /api/episodes` 问诊列表

查询参数：

| 参数 | 说明 |
| --- | --- |
| `page` / `size` | 分页 |
| `status` | 逗号分隔的状态过滤，如 `saved`、`ready,clarifying,generating` |
| `triage` | 逗号分隔的档位过滤 |

响应为分页结构，`records` 为 `EpisodeSummary` 数组，按 `created_at` 倒序。

用途：档案历史列表传 `status=saved`；问诊 tab 的"继续上次"传 `status=clarifying,generating&size=3`（完成即归档，`ready` 不再是持久状态）。

### 5.6 `GET /api/episodes/{id}` 问诊详情

返回 `EpisodeDetail`。用于页面恢复、只读查看与断流后的整包兜底，不触发任何生成。

错误：2004 不存在、已过期或不属于当前用户（不区分，避免泄露存在性）。

`degraded` 与 `gate.fallback` 的含义：`degraded=true` 表示走了兜底模板（平台不可用、超时、草稿不合规），`gate.fallback=true` 是它在闸门摘要里的同义标记；引用全部核验失败只让 `conditions` 为空，不算降级。

### 5.7 归档与提醒：生成完成即自动

原 `POST /api/episodes/{id}/save` 端点已移除。问诊生成完成（含红旗短路与兜底模板）即自动归档并按档位创建提醒，不再依赖任何手动确认；引用闸门在落库前已逐字核验，让用户再「核对」一遍只是免责仪式，而提醒挂在手动归档上会让没点确认的人静默失去复查闭环。

| 档位 | 自动动作 |
| --- | --- |
| `self_observe` | 建随访提醒，`created_at` + 48 小时 |
| `clinic` | 建复查提醒，`created_at` + 3 天的 09:00（策略在后端，前端不再选日期） |
| `emergency` | 只归档，不建提醒 |

归档即 `status=saved` 且 `saved_at` 置位；幂等重放不重复归档、不翻倍提醒，已有待处理提醒保持原样。未走完的问诊（`generating`/`clarifying`/`failed`）不归档，到期由清理任务物理删除。

### 5.8 `DELETE /api/episodes/{id}`

删除问诊，连带删除其引用、随访、问答记录与事件记录。已保存的问诊同样可删。响应 `data: null`。错误：2004。

### 5.9 `GET /api/episodes/{id}/constraints` 约束详情

返回可复算的过程证据，不返回一致率等离线指标。

```json
{
  "complaint": "这两天一直流鼻涕，嗓子有点干",
  "normalized": {},
  "self_attribution": { "text": "可能是着凉了", "removed": true },
  "diff": {
    "removed_conditions": [
      { "name": "过敏性鼻炎", "reason": "citation_unverified" }
    ],
    "blocked_expressions": [
      { "type": "dosage", "segment": "prep" }
    ]
  },
  "actions": {}
}
```

`reason` 取值：`citation_unverified` 引用核不上、`not_in_vocab` 名称不在词表、`over_limit` 超出 5 条。`blocked_expressions[].type` 取值：`dosage` 剂量、`prescription` 处方、`diagnosis` 确诊与断言；只给类型与所在段落，不返回被拦截的原文。

错误：2004、2005（问诊尚未生成结果）。

### 5.10 `POST /api/episodes/{id}/qa` 受限问答

针对本次结论的追问，一次一问，非流式。不重新检索、不调用模型，答案由该问诊的引用池与模板拼装。

请求：

```json
{ "question": "为什么建议门诊而不是先观察" }
```

`question` 长度 1–200。

响应 `data` 为 `QaTurn`（见 2.14），另外带两个字段：

```json
{
  "turn": {},
  "remaining_turns": 7,
  "escalation": null
}
```

| 情形 | 响应 |
| --- | --- |
| 归类成功 | `intent` 为 `evidence`/`recap`/`next_steps`，`answer` 三段齐全 |
| 超出可答范围 | `intent=out_of_scope`，`answer.basis` 为空，`next_text` 提示重新描述 |
| 输入命中红旗 | `intent=red_flag`，`answer=null`，`escalation={ "complaint_prefill": "原主诉 + 这句话" }`，前端据此打开新问诊 |
| 超过 10 次 | 409 + 2008 |

规则：

- 只读该问诊已核验的引用，`basis` 逐字核对，核不上删掉该条；全部核不上时降级为 `recap`。
- 回答不含档位判断、不含药名与剂量，也不修正原结果。
- 记录写入 `qa_turn`，随问诊删除，包含在导出内容里。

错误：2004 不存在、2005 状态不是 `ready`/`saved`、2008 次数超限。

### 5.11 流式事件

所有流式接口使用同一套事件。事件名固定 7 种，每条带 SSE `id`（从 1 递增）。

| 事件 | 载荷 | 说明 |
| --- | --- | --- |
| `stage` | `{ episode_id, stage, text, progress }` | `stage` ∈ `normalize`/`clarify`/`retrieve`/`draft`/`gate`/`compose`；`text` 为模板文案，`progress` 为 0–100 |
| `question` | `{ episode_id, round, round_limit, missing_fields, questions }` | 需要追问时下发，之后流结束 |
| `citation` | `{ episode_id, items }` | 引用池，元素为 `{doc_title, section, quote}` |
| `result_section` | `{ episode_id, section, payload }` | `section` ∈ `triage`/`department`/`conditions`/`prep`/`disclaimer` |
| `done` | `{ episode_id, triage, conditions_count, gate, degraded }` | 正常结束 |
| `error` | `{ episode_id, code, message, retryable }` | 失败结束，`code` 见第 12 节 |
| `heartbeat` | `{ ts }` | 空闲每 15 秒发送一次 |

帧格式示例：

```
id: 1
event: stage
data: {"episode_id":9001,"stage":"normalize","text":"正在理解你的描述","progress":10}

```

服务端约束：

- 响应头包含 `Content-Type: text/event-stream`、`Cache-Control: no-cache`、`Connection: keep-alive`、`X-Accel-Buffering: no`；关闭压缩与网关缓冲。
- 正文只在 `gate` 阶段完成后通过 `result_section` 下发，任何模型原文不得进入事件流。
- 一次流必须以 `done` 或 `error` 结束，不能静默关闭。
- 生成超过 60 秒以 `error`（4002）结束；`retryable` 为 `true`。
- 事件不缓存、不重放。断线后前端调 `GET /api/episodes/{id}` 取整包，`status=generating` 时轮询，间隔 3 秒，上限 60 秒。
- 流建立前的鉴权与参数错误用普通 JSON 信封返回，状态码 400/401/409，不进入 SSE。

前端约束（`src/request/`）：

- 使用 `uni.request({ enableChunked: true })` 并监听 `requestTask.onChunkReceived`；H5 与小程序共用一条实现，小程序要求基础库 ≥2.20.2。
- 分片是 `ArrayBuffer`，需自行按 `\n\n` 分帧、缓存半行，并自行处理 UTF-8 多字节被切断的情况（小程序端不保证有 `TextDecoder`）。
- 流式请求需放宽超时（`manifest.json` 的 `networkTimeout` 默认 60 秒），收到 `done`/`error` 后主动 `abort`。
- 页面不直接调 `uni.request`，流式封装放在 `src/request/sse.ts`。

## 6. 档案

### 6.1 `GET /api/profile`

响应 `data: { "profile": Profile | null }`。`profile` 为 `null` 表示尚未初始化，前端跳引导页。档案首页不要用本接口拼装，改用 `GET /api/archive/overview`。

### 6.2 `GET /api/profile/privacy`

返回当前隐私政策版本与用户的同意记录。注册前的版本信息用 `GET /api/meta/privacy` 取，本接口只给已登录用户看自己的同意记录。

```json
{
  "current_version": "2026-11-01",
  "consented_version": "2026-11-01",
  "consented_at": "2026-11-20 10:00:00",
  "outdated": false
}
```

`outdated` 为 `true` 时前端在首次进入时提示重新确认，未确认前提交主诉返回 1006。

### 6.3 `PUT /api/profile`

部分更新：只提交需要修改的字段，未出现的字段保持不变；提交 `""`、`[]` 或 `null` 表示清空。

```json
{
  "birth_date": "1990-06-12",
  "sex": "male",
  "city_code": "310100",
  "city_name": "上海市",
  "conditions": ["高血压"],
  "allergies": ["青霉素"],
  "name": "张三"
}
```

规则：

- `birth_date` 不得晚于今天，且早于 1900-01-01 视为无效。
- `sex` 必须属于枚举。
- `city_code` 与 `city_name` 需同时提交，`city_code` 使用行政区划码；选择"不确定"时两者都清空。
- `conditions` 与 `allergies` 为字符串数组，每项 ≤20 字，最多 10 项；`allergy_note`、`condition_note` ≤200 字。
- 响应返回更新后的 `Profile`。

错误：400（字段不合规，`message` 指明字段）。

## 7. 体征

### 7.1 `GET /api/vitals`

查询参数 `kind`（可选）、`page`、`size`。响应为分页结构，`records` 为 `Vital`，按 `measured_at` 倒序。

### 7.2 `POST /api/vitals`

```json
{ "kind": "bp", "measured_at": "2026-11-28 08:10:00", "systolic": 128, "diastolic": 82, "pulse": 72 }
```

| 类型 | 必填 | 范围 |
| --- | --- | --- |
| `height` | `height_cm` | 50–250 |
| `weight` | `weight_kg` | 2–300，保留 1 位小数 |
| `bp` | `systolic`、`diastolic`；`pulse` 选填 | 收缩压 60–260、舒张压 30–160、脉搏 30–220 |

- `measured_at` 不得晚于当前时间。
- 身高为单值语义：新增身高会覆盖旧值（服务端保留最新一条）。
- 错误：3002 数值超出范围。

### 7.3 `PUT /api/vitals/{id}` / `DELETE /api/vitals/{id}`

修改同一 `kind` 的数值与测量时间；删除为硬删。删除不影响已生成问诊的快照。错误：3002、404。

## 8. 用药

### 8.1 `GET /api/medications`

查询参数 `kind`、`status`（均可选）。响应 `data: { "records": Medication[] }`，按 `status` 与 `started_on` 排序，不分页（每人条数有限）。

### 8.2 `POST /api/medications`

```json
{ "name": "氨氯地平", "dosage_text": "1 片", "frequency_text": "一天一次", "kind": "long_term", "started_on": "2025-03-01" }
```

- `name` 1–40 字；`dosage_text` ≤40 字；`frequency_text` ≤40 字；`dosage_text` 为纯文本，服务端不解析、不换算。
- `kind=short_term` 时 `ended_on` 必填且不早于 `started_on`。
- 错误：3003。

### 8.3 `PUT /api/medications/{id}`

可修改 `name`、`dosage_text`、`frequency_text`、`ended_on`、`status`。置 `status=stopped` 时，其用药计划一并停用。

### 8.4 `DELETE /api/medications/{id}`

硬删，连带删除其计划与未处理提醒。

### 8.5 `GET /api/medication-plans` / `POST /api/medication-plans`

```json
{ "medication_id": 5, "times": ["08:00"], "started_on": "2026-11-20", "ended_on": "2026-12-20", "note": "饭后吃" }
```

- `times` 长度 1–4，格式 `HH:mm`，不能重复；服务端按时间升序返回。
- 只能绑定属于当前用户的用药记录。
- `ended_on` 缺省为 `started_on` + 30 天。

### 8.6 `PUT /api/medication-plans/{id}` / `DELETE /api/medication-plans/{id}`

可修改 `times`、`started_on`、`ended_on`、`note`、`status`。删除为硬删并清理未处理提醒。

## 9. 档案聚合

### 9.1 `GET /api/archive/overview`

档案首页一次性取数，避免首屏多次请求。

```json
{
  "profile": {},
  "vitals": {
    "latest_height_cm": 175,
    "latest_weight_kg": 70.5,
    "bmi": 23.0,
    "latest_bp": { "measured_at": "2026-11-28 08:10:00", "systolic": 128, "diastolic": 82, "pulse": 72 }
  },
  "trend_summary": { "episodes_90d": 3, "latest_triage": "clinic" },
  "pending": { "total": 2, "medication": 1, "followup": 1, "recheck": 0 }
}
```

`bmi` 在缺少身高或体重时为 `null`，由服务端计算，保留 1 位小数。

### 9.2 `GET /api/archive/trend`

查询参数 `days`（默认 90，最大 365）、`limit`（默认 10，最大 50）。

```json
{
  "triage_points": [{ "at": "2026-11-30 21:14:00", "triage": "self_observe" }],
  "weight_points": [{ "at": "2026-11-20", "weight_kg": 70.5 }],
  "bp_points": [{ "at": "2026-11-28 08:10:00", "systolic": 128, "diastolic": 82 }],
  "symptom_keywords": [{ "term": "流鼻涕", "count": 2 }]
}
```

- `triage_points` 只取已保存的问诊。
- `weight_points` 同一天多次测量取最后一次。
- `symptom_keywords` 取自结构化字段，按次数降序，最多 5 条。
- 无数据时各数组为空，前端显示"数据不足"。

## 10. 提醒

### 10.1 `GET /api/reminders`

查询参数 `date`（默认今天，`yyyy-MM-dd`）、`kind`（可选）。按日返回，不分页。

```json
{
  "groups": {
    "medication": [
      {
        "id": 77,
        "kind": "medication",
        "due_at": "2026-12-01 08:00:00",
        "status": "pending",
        "title": "氨氯地平 1 片",
        "body": "你录入的用法，请按医嘱或说明书使用。",
        "snooze_count": 0
      }
    ],
    "followup": [],
    "recheck": []
  },
  "pending_count": 1
}
```

`title` 与 `body` 由后端模板拼装，前端直接展示，不自行组织文案。

### 10.2 `POST /api/reminders/{id}/respond`

按提醒类型使用不同动作。

| 类型 | 请求体 | 响应 |
| --- | --- | --- |
| `followup` | `{"action":"answer","answers":{"relieved":"no","visited":"no","new_symptom":"yes"},"note":"咳嗽加重"}` | `{ "status": "done", "advice": { "level": "clinic", "text": "建议尽快就诊" }, "supplement": Supplement | null }` |
| `recheck` | `{"action":"visited"}`、`{"action":"planned"}`、`{"action":"improved"}` | `{ "status": "done" }` 或 `{ "status": "pending" }`（`planned` 保留待办） |
| `medication` | `{"action":"taken"}`、`{"action":"skipped"}`、`{"action":"snooze"}` | `{ "status": "done" }`，`snooze` 返回 `{ "status": "pending", "due_at": "..." }` |

规则：

- `followup.answers` 三个键必填：`relieved` 取 `yes`/`no`/`worse`，`visited` 取 `yes`/`no`，`new_symptom` 取 `yes`/`no`；`note` ≤200 字。
- `recheck` 的三个动作语义：`visited` 已就诊（关闭）、`planned` 还没去但要安排（保留待办并允许改期）、`improved` 已好转（关闭）。
- `snooze` 最多两次，第三次返回 409 + 3004。
- 已处理的提醒再次提交返回 3004。
- 随访回答只生成随访记录，不创建新问诊；`advice.level` 由固定八条优先级规则得出，取值 `self_observe`/`clinic`/`emergency`/`closed`。
- `supplement` 是随访的第二层：仅当 `advice.level` 落在 `clinic`（含"已就诊但加重"）时生成，急诊与关闭态为 `null`。字段与校验见 2.13。
- 第二层模型调用超时（>8 秒）或字段校验不通过时，`supplement` 为 `null`，响应仍为成功，随访记录标 `degraded`，不重试。
- `supplement` 不参与 `advice.level` 的判定，也不允许改写第一层文案。

## 11. 数据管理

### 11.1 `GET /api/export`

同步生成导出包并返回一次性下载地址。

```json
{ "url": "https://example.com/api/export/9f2b7c.zip", "expires_at": "2026-12-02 10:00:00", "size_bytes": 182734 }
```

内容为全量 JSON（档案、体征、用药、计划、问诊、引用、随访、问答、提醒）与问诊记录 CSV。地址 24 小时有效。数据量过大（超过 50 MB）返回 3005。

### 11.2 `GET /api/export/{token}`

按 11.1 返回的地址下载文件，无需 `Authorization`，凭不可猜测的 `token` 鉴权，过期或已使用返回 404。响应为 `application/zip` 附件。

### 11.3 `DELETE /api/data`

请求 `{ "confirm": "删除" }`。清空档案、体征、用药、计划、问诊、引用、随访、提醒、日报与事件记录，账号保留。响应 `{ "cleared": { "episodes": 3, "vitals": 5, "medications": 2, "reminders": 4 } }`。

错误：3006 确认文本不匹配（HTTP 400）。

### 11.4 `DELETE /api/account`

请求 `{ "confirm": "删除" }`。清空全部数据并注销账号，所有令牌立即失效。响应 `data: null`。

删除一律硬删，不做软删，不可恢复；服务端只记录一条无内容的操作日志（时间与用户号哈希）。

## 12. 错误码

### 12.1 通用

| 码 | HTTP | 含义 |
| --- | --- | --- |
| 0 | 200 | 成功 |
| 400 | 400 | 参数不合法 |
| 401 | 401 | 未认证 |
| 403 | 403 | 无权限 |
| 404 | 404 | 资源不存在 |
| 500 | 500 | 服务异常 |

### 12.2 业务号段

| 码 | HTTP | 含义 | 可重试 |
| --- | --- | --- | --- |
| 1001 | 400 | 手机号或密码格式不合规 | 是 |
| 1002 | 409 | 手机号已注册 | 否 |
| 1003 | 401 | 账号或密码错误 | 是 |
| 1004 | 401 | 访问令牌过期 | 是（静默刷新） |
| 1005 | 401 | 刷新令牌无效 | 是（重新登录） |
| 1006 | 403 | 未同意隐私政策或同意版本过期 | 否 |
| 1007 | 403 | 账号停用或演示账号只读 | 否 |
| 1008 | 429 | 登录尝试过多 | 是（等待） |
| 2001 | 400 | 主诉为空 | 是 |
| 2002 | 400 | 主诉超长 | 是 |
| 2003 | 409 | 追问轮次已达上限 | — |
| 2004 | 404 | 问诊不存在或已过期 | 否 |
| 2005 | 409 | 问诊状态不允许该操作 | 否 |
| 2006 | 409 | 幂等键冲突 | 是（换新键） |
| 2007 | 400 | 追问答案字段不合法 | 是（重拉问题） |
| 2008 | 409 | 该问诊的问答次数已达上限（10 次） | 否 |
| 3001 | 409 | 档案必填项缺失 | 否 |
| 3002 | 400 | 体征数值超出范围 | 是 |
| 3003 | 400 | 用药记录或计划不合法 | 是 |
| 3004 | 404/409 | 提醒不存在或已处理 | 否 |
| 3005 | 413 | 导出数据过大 | 否 |
| 3006 | 400 | 删除确认不匹配 | 是 |
| 4001 | 502 | 平台不可用 | 是 |
| 4002 | 504 | 平台超时 | 是 |
| 4003 | 503 | 平台限流或额度不足 | 是（延后） |
| 4004 | 502 | 草稿结构不合规 | 是 |
| 5001 | 404 | 当日还没有日报 | 是（先调 `POST /api/daily/generate`） |
| 5002 | 409 | 当日设备记录不足，暂不生成小结 | 否（等真实数据接入） |
| 5003 | 409 | 当日小结待人工核实 | 否 |
| 5004 | 400 | 日报输入未通过平台校验 | 否（确定性失败） |

平台类错误（4001–4004）在问诊接口里也表现为放行兜底结果：HTTP 仍返回 200 的流，流内以 `done`（含 `degraded=true`）结束，同时在 `stage` 文案里说明已采用保守建议；只有在流建立之前就失败时才直接返回错误信封。

## 13. 状态与业务规则摘要

完整规则见《清诉主流程》，这里只列接口必须执行的部分。

| 规则 | 接口侧表现 |
| --- | --- |
| 主诉原文逐字保存 | `complaint_text` 不再被任何接口修改 |
| 红旗优先于澄清 | 命中红旗时流内直接出 `stage` 与结果，不下发 `question` |
| 澄清轮次上限 5，每轮 ≤5 问 | 第 5 轮后 `clarify` 返回 2003，或流内直接进入生成 |
| 引用必须逐字核验 | 未通过的条目不出现在 `result.conditions`，在约束详情里作为 `removed_conditions` 出现 |
| 兜底必须有档位 | 4001/4002/4004 时 `result.triage` 为 `clinic`，科室为全科医学科 |
| 未保存问诊保留 30 天 | `expires_at = created_at + 30 天`，到期后 `GET` 返回 2004 |
| 体征不参与定档 | 体征只进入 `vitals_snapshot` 与上下文文本，不改变 `triage` |
| 模型摘要不落库 | `profile` 与档案页的摘要文本由服务端模板拼装 |
| 随访两层 | 第一层规则表给档位与文案；第二层只给 `watch_for`/`prepare_idx`/`next_question`，不含档位、时间窗、药名与剂量 |
| 受限问答不重新检索 | 只读该问诊已核验的引用；越界归 `out_of_scope`，红旗转新问诊 |
| 提醒仅站内 | 接口不提供推送与订阅消息 |

## 14. 实现约定

### 14.1 后端

| 项 | 约定 |
| --- | --- |
| 包结构 | `app/account`（认证、档案、数据管理）、`app/archive`（体征、用药、计划、聚合）、`app/episode`（问诊、流式、约束详情）、`app/reminder`（随访、复查、用药提醒）、`app/daily`（每日健康关怀）、`app/agent`（AgentArts 客户端与闸门），各包含 `router.py`、`service.py`、`schema.py`、`models.py` |
| 路由注册 | 各包 `router` 在 `app/api/__init__.py` 汇总，`/api` 前缀只在 `main.py` 出现一次 |
| 鉴权依赖 | `Depends(get_current_user)` 放在需要鉴权的 router 上，流式接口同样适用 |
| 响应包装 | 成功用 `ok(data)`，业务错误抛 `BizException(ErrorCode.XXX)`，不手写 JSON |
| 错误码扩展 | `ErrorCode` 需要新增 4 位业务码，并把 `http_status` 从"值即状态码"改为显式映射表；否则 4 位码会被映射成 500 |
| 流式实现 | `StreamingResponse` 生成器逐条 `yield` 已格式化的 SSE 帧；生成器内部捕获业务错误并转为 `error` 事件，不抛出 |
| 超时 | 单次生成上限 60 秒，平台 HTTP 客户端超时要小于该值，留出闸门时间 |
| 数据库 | 11 张表（见《清诉主流程》附录 A），只通过 Alembic 迁移创建；新模型要 import 进 `alembic/env.py` |
| 时间 | 统一 `Asia/Shanghai`，出参用 `yyyy-MM-dd HH:mm:ss` 字符串；模型列用 `TIMESTAMPTZ` |
| 测试 | 每个 router 一个 pytest 文件，用合成数据，不碰真实健康信息；流式接口至少测一条正常流与一条 `error` 流 |
| 问答模块 | 归类、引用挑选、模板拼装放在 `app/episode/qa.py`，不依赖模型客户端；每条回答的可测断言是"引用来自该问诊引用池""不改档位" |
| 定时任务 | 用药提醒生成与超时、随访与复查扫描、短期药到期、未保存清理、演示数据清理，进程内调度，不引入 Redis |

### 14.2 前端

| 项 | 约定 |
| --- | --- |
| 请求入口 | 只走 `src/request/index.ts`；流式走 `src/request/sse.ts` |
| 接口函数 | 按域放在 `src/api/`，一个文件一个域，函数名与路径对应（`createEpisode`、`saveEpisode`、`listReminders`） |
| 类型 | 与本文对象同名（`Profile`、`Vital`、`EpisodeDetail`、`Result`），手写在 `src/api/` 内，暂不生成 |
| 错误处理 | 只判断 `code`，文案取本地映射表；1004 静默刷新一次后重放，1005 跳登录 |
| 状态 | Pinia store 存登录态与当前问诊 id；页面不缓存结果，重进用 `GET /api/episodes/{id}` |
| 图表 | 趋势页用 `@qiun/ucharts`，该页放分包 |

## 15. 未纳入本次接口

| 项 | 原因 |
| --- | --- |
| 开放式健康问答、跨问诊聊天 | 会绕开引用核验与模板锁定，只提供受限问答（5.10） |
| 微信登录、短信验证码 | 需要 appid、企业资质与模板报备 |
| 订阅消息、短信推送 | 同上，当前只有站内提醒 |
| 定位取城市 | 隐私与合规成本高于收益 |
| 医院、医生、挂号接口 | 不在产品边界内 |
| 跨用户数据聚合 | 同上 |
| 接口限流与配额 | 当前只用进程内计数处理登录失败，后续需要再引入 Redis |
| 前端类型自动生成 | 候选 `openapi-typescript`，等接口稳定后再接 |

## 16. 每日健康关怀

日报回顾「已经发生的一天」：手表指标由后端合成，档案摘要由后端组装，前端不提交任何指标或档案字段（信任边界见 api-agentarts.md 16.8.8 第 1 条）。两个接口都是非流式，平台单次调用预算 60 秒，业务层不重试。

### 16.1 `POST /api/daily/generate`

请求体可省略，只接受一个字段：

```json
{ "report_date": "2026-11-30" }
```

- `report_date` 省略时取 `Asia/Shanghai` 的当天；格式 `yyyy-MM-dd`，不得晚于今天，否则 400 + 400。
- 同日重复调用按当前档案与合成数据重算并覆盖同一份报告（用户＋日期＋工作流版本唯一），不产生第二条当前报告；迟到结果不覆盖更新的报告。
- 只读后端数据：指标来自合成手表数据（`data_source=mock`），档案来自档案表。`watch_data`、`health_archive`、`user_id` 等字段不接受，出现即 400 + 400。

响应 `data`：

```json
{
  "report_date": "2026-11-30",
  "status": "ready",
  "degraded": false,
  "data_source": "mock",
  "workflow_version": "2026-11-24.daily-companion.2",
  "summary": {
    "title": "今天的健康小结",
    "greeting": "今天辛苦了，我们一起回看设备留下的记录。",
    "highlights": [
      {
        "id": "metric:steps",
        "label": "步数",
        "text": "今天设备记录了4600步。",
        "source_refs": ["watch_data.metrics.steps"]
      },
      {
        "id": "metric:sleep_duration",
        "label": "睡眠时长",
        "text": "设备记录的睡眠时长为435分钟。",
        "source_refs": ["watch_data.metrics.sleep_duration"]
      }
    ],
    "health_connections": [
      {
        "id": "connection:GUIDANCE-001",
        "label": "与个人照护目标的联系",
        "text": "关于“高血压（合成演示）”的原有安排：今天的步数记录落在档案已确认的个人目标区间内。",
        "source_refs": ["health_archive.care_guidance.GUIDANCE-001"],
        "record_id": "MEDICAL-001",
        "condition_id": "CONDITION-001"
      }
    ],
    "gentle_reminders": [
      {
        "id": "quality",
        "label": "数据完整性",
        "text": "当天有部分指标未记录，缺失数据不代表正常。",
        "source_refs": []
      }
    ],
    "tomorrow_actions": [
      {
        "id": "action:1",
        "label": "明日安排",
        "text": "按既有安排继续每天散步，不必因为单日数据临时加量。",
        "source_refs": ["health_archive.care_guidance.GUIDANCE-001"],
        "record_id": "MEDICAL-001",
        "condition_id": "CONDITION-001"
      }
    ],
    "closing": "照顾好自己。",
    "limitations": "单日设备变化不能判断疾病好转或恶化。"
  },
  "data_quality": { "wear_minutes": 1380, "available_metric_ids": ["steps"], "coverage_limited": false },
  "used_record_ids": ["ep12"],
  "created_at": "2026-11-30 21:14:00",
  "updated_at": "2026-11-30 21:14:00"
}
```

- `data_source` 当前恒为 `mock`（真实设备适配在后续阶段），前端必须展示模拟标记，模拟记录不得混入真实档案或告警。
- `degraded` 由内部 `status` 折出，前端不比较字符串：`status=degraded` 时正文是模板兜底，加降级标记后照常展示。
- `summary` 的板块文案由工作流模板生成，后端只核对板块、来源与日期，不改写；`used_record_ids` 必须能在当前档案里回查。
- `summary` 的四个内容板块 `highlights`、`health_connections`、`gentle_reminders`、`tomorrow_actions` 都是**对象数组**，不是字符串数组；某个板块可以合法地为空数组（例如当天所有指标都正常时不产生温和提醒），前端不得因此判定报告异常。每个条目的字段：

| 字段 | 约定 |
| --- | --- |
| `id` | 当前小结内唯一；`connection:` 前缀表示与档案照护安排的关联 |
| `label` | 板块内的短标签（类别名），用于分组或辅助展示 |
| `text` | 面向用户的正文，恒为非空字符串；展示层只渲染这个字段 |
| `source_refs` | 逻辑溯源标识数组，可为空（如数据完整性提醒）；不是 URL，也不是 JSONPath |
| `record_id` / `condition_id` | 仅出现在 `health_connections` 与 `tomorrow_actions`；指向当前用户档案内的问诊/病历与已确认疾病，仅供追溯，展示层不必渲染 |

以上形状于 2026-11-27 由真实运行时响应核对，与 `api-agentarts.md` 16.8.7 的样例一致。早期版本的本节示例把四个板块写成空数组、未给出条目形状，曾导致前端按字符串数组实现无法渲染正文。
- `workflow_version` 是平台回显的 DSL 版本，前端只展示或记日志，不当契约断言。

### 16.2 `GET /api/daily?date=2026-11-30`

查询参数 `date`（默认今天，规则同 16.1）。响应 `data` 与 16.1 相同，返回该日**最新写入**的一份；平台升版后同一天可能留有多个版本的行，本接口只取 `updated_at` 最新的一行。本接口不触发生成，没生成过就返回 5001。

### 16.3 status → 信封

| 报告 status | `code` | HTTP | 前端表现 |
| --- | --- | --- | --- |
| `ready` | 0 | 200 | 正常展示 |
| `degraded` | 0 | 200 | 展示并加降级标记（`degraded=true`） |
| `data_insufficient` | 5002 | 409 | 温和说明当天记录不足，不写「一切正常」 |
| `review_required` | 5003 | 409 | 待人工核实，暂停活动任务，不替代既有急诊处理 |
| `invalid_input` | 5004 | 400 | 输入未通过平台校验，不落库，确定性失败不重试 |

两个接口共用这张表；读不到报告返回 5001（HTTP 404）。5002/5003 用 409 而不是 200：请求本身合法，是当前状态（设备记录不足、待人工核实）不足以给出小结，且这两种状态下没有可展示的正文，前端按 `code` 取本地文案。
