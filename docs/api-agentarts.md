# 清诉工作流 API 对接

更新日期：2026-11-21。

本文件定义后端调用三个AgentArts工作流的接口、请求示例和响应处理。与[清诉业务API文档](api.md)配套：本文引用的第1–15节均指该文档中的公开业务API，本文件保留第16节编号以便对照。

实际凭据与鉴权实现已单独放入《auth-info-backend-only.md》，由负责人私下交付。本文件和公开示例包不包含明文密钥。拆分是为了分别维护与交接；实际发送请求仍要由后端注入认证信息。

## 16. 后端调用 AgentArts 工作流

更新日期：2026-11-21。本节在配套业务API第1–15节的前后端 HTTP 契约之外，补充**后端 → AgentArts**的内部契约。前端仍只调用清诉自己的 `/api`，不接触平台密钥、模型原文、内部证据池或平台执行事件。

本节依据用户提供的三个调用路径、本地交付的三份 DSL 和其代码节点编写。调用路径已登记；**未使用密钥发起真实网络调用，尚未验证这些运行时部署的具体工作流版本**。本地 DSL 预期版本如下，后端联调时必须校验最终结果中的版本：

| 工作流 | 请求 schema_version | 响应 schema_version | 本地交付 workflow_version |
| --- | --- | --- | --- |
| Triage-Workflow-MainFlow | `clear-complaint.triage.request.v1` | `clear-complaint.triage.workflow.v1` | `2026-11-21.mainflow-io.3` |
| Profile-Intake-Workflow | `clear-complaint.profile-intake.request.v1` | `clear-complaint.profile-intake.workflow.v1` | `2026-11-21.profile-intake.1` |
| Followup-Supplement-Workflow | `clear-complaint.followup-supplement.request.v1` | `clear-complaint.followup-supplement.workflow.v1` | `2026-11-21.followup-supplement.1` |

本节定义对接方式，不代表已实现后端调用客户端、归一化、数据库、正式受控目录或新增公开路由。示例全部为软件合成数据，不能作为真实医学证据或临床规则。

### 16.1 调用地址、配置与职责

三个地址均使用 `POST`。严格使用当前调用路径，不复用旧 Health-Target、Stateful-Update 或适配服务地址，也不自行添加旧示例中的 `?endpoint=Latest`。

**Profile-Intake-Workflow**

```text
https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-b86c2f610cf64a89b8e215050e9e4508/invocations
```

**Followup-Supplement-Workflow**

```text
https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-6a31c4e6059f4696ab5d0f458220c7bf/invocations
```

**Triage-Workflow-MainFlow**

```text
https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-560ea305ef5542a79edd582e6da0fc7c/invocations
```

后端公开配置记录调用地址、运行模式和密钥变量名；凭据值、获取方法及请求头构造统一放到另行私密交付的《auth-info-backend-only.md》，不进入本文件和公开示例包。正式请求仍必须完成运行时认证，不能因示例没有明文凭据而省略认证。

```dotenv
AGENTARTS_PROFILE_INTAKE_URL=https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-b86c2f610cf64a89b8e215050e9e4508/invocations
AGENTARTS_PROFILE_INTAKE_API_KEY=
AGENTARTS_FOLLOWUP_SUPPLEMENT_URL=https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-6a31c4e6059f4696ab5d0f458220c7bf/invocations
AGENTARTS_FOLLOWUP_SUPPLEMENT_API_KEY=
AGENTARTS_TRIAGE_URL=https://defaultgw-mqytamjqmn.cn-southwest-2.huaweicloud-agentarts.com/runtimes/agent-arts-560ea305ef5542a79edd582e6da0fc7c/invocations
AGENTARTS_TRIAGE_API_KEY=
AGENTARTS_INVOKE_MODE=published
```

KEY 必须通过私密渠道交付，文档与仓库只登记变量名，不填写真实值；变量名已同步登记在 `backend/.env.example`。三个运行时分别持有各自的 Key，不能假定共用，也不能与 MaaS 模型密钥混用。这些配置名尚未接入后端 `Settings`，URL 登记也不证明云端版本与接口联调已经验收。

| 清诉业务入口 | 调用平台的时机 | 后端保留的责任 |
| --- | --- | --- |
| 第5节创建、澄清、跳过或重试问诊 | 合法进入 `generating`，未命中红旗，需要生成草稿 | 身份/归属、归一化、固定追问、规则、幂等、最终闸门/模板、存储和兜底 |
| 档案引导对话服务，公开入口见16.4的待实现建议 | 选择下一采集字段，或抽取本轮单字段回答 | 临时状态、原话、归属、确认表单、最终保存；不自动写正式档案 |
| 第10.2节 `POST /api/reminders/{id}/respond` | 第一层规则完成，满足16.5的第二层适用条件 | 第一层建议、受控目录、8秒预算、准备项映射、随访记录和降级 |

### 16.2 通用 HTTP 请求与平台 SSE 解包

#### 16.2.1 请求头

下面仅列业务与追踪请求头。发送前还要合并后端私有配置提供的运行时请求头；相关实现和凭据见私密鉴权文档，不能把本片段当成无需认证的完整请求。

```http
Content-Type: application/json
Accept: text/event-stream
X-Invoke-Mode: published
x-hw-agentarts-session-id: <后端生成的会话UUID>
X-Request-Id: <本次HTTP尝试的追踪UUID>
```

- `published`用于已部署版本；排查开发版本时才显式使用 `debug`。不能把调试版本与正式验收结果混为一谈。
- 平台会话ID只用英文、数字、`-`、`_`，最多64字符；后端生成不带个人信息的UUID，按用户和业务会话隔离，三类工作流分别保存映射。
- 业务 `session_id/episode_id/followup_id`、平台会话ID、请求追踪ID分别管理。同一次逻辑请求的 `request_id` 和幂等键稳定；不同网络尝试可以有不同的追踪ID。
- 同一业务会话可以沿用平台会话ID，但每次仍发送完整可信快照。平台会话ID不替代数据库状态、访问控制或第1.6节幂等。[官方请求参数](https://support.huaweicloud.com/api-agentarts/InvokeRuntime.html)

#### 16.2.2 请求体：三条工作流完全共用这一层

业务对象见16.3–16.5。开始节点的 `request_json` 是 **String**，因此HTTP外层的 `inputs.request_json` 必须是JSON字符串，不是对象。原生 `query`不参与这三条工作流处理，可省略；不要把用户回答单独放进 `query`。

下面是可直接发送的完整“开始档案采集”HTTP请求体：

```json
{
  "inputs": {
    "request_json": "{\"schema_version\": \"clear-complaint.profile-intake.request.v1\", \"session_id\": \"SYNTHETIC-PROFILE-001\", \"request_id\": \"SYNTHETIC-INTAKE-001\", \"action\": \"start\", \"as_of_date\": \"2026-11-21\", \"form_snapshot\": {}, \"medication_drafts\": null, \"active_field\": null, \"user_input\": \"\", \"skipped_fields\": [], \"unknown_fields\": [], \"required_fields\": [\"birth_date\", \"sex\"]}"
  }
}
```

后端组装的等价写法：

```python
import json

# business_request是16.3、16.4或16.5所列的业务对象。
payload = {
    "inputs": {
        "request_json": json.dumps(business_request, ensure_ascii=False, allow_nan=False)
    }
}
# HTTP客户端以JSON方式发送payload；不要把payload再次包成字符串。
```

在平台控制台手工试运行时，直接把业务对象正文粘贴到 `request_json` 输入框，**不用手动转义**。只有HTTP传输层需要外部对象包裹和字符串序列化。

Postman：方法选POST，URL与工作流对应，Body选raw/JSON并粘贴对应 `*.http.json`。按私密鉴权文档完成认证配置后再发送；本文件不导出凭据。平台截图里的 `query: 你好` 只是通用演示，不能替代本项目的业务请求。

Python联调示例见16.2.4。截图中的静态会话ID改为后端按业务会话保存的ID，不能所有用户共用。

#### 16.2.3 从平台事件中提取最终内部结果

平台返回SSE，不能对整段响应直接调用 `.json()`，也不能把每个网络分片当成一条完整JSON。处理方式：按SSE帧缓存和拼接 `data:` 行，解析JSON事件；以 `event=workflow_finished` 的成功终态为准，取 `data.outputs.responseContent`，再将其中的JSON文本解析成16.3–16.5的内部对象。DSL里的End槽名 `response_content`、内部代码变量 `result_json`与HTTP最终包装字段不是同一层。

成功示意帧，仅用于说明外层结构，`responseContent`中是完整业务JSON：

```text
data: {"event": "workflow_finished", "data": {"status": {"code": 1, "desc": "succeeded"}, "outputs": {"responseContent": "{\"schema_version\": \"clear-complaint.profile-intake.workflow.v1\", \"workflow_version\": \"2026-11-21.profile-intake.1\", \"session_id\": \"SYNTHETIC-PROFILE-001\", \"request_id\": \"SYNTHETIC-INTAKE-001\", \"status\": \"needs_answer\", \"form_draft\": {\"name\": null, \"birth_date\": null, \"sex\": null, \"city_code\": null, \"city_name\": null, \"conditions\": null, \"condition_note\": null, \"allergies\": null, \"allergy_note\": null}, \"medication_drafts\": null, \"form_patch\": {}, \"skipped_fields\": [], \"unknown_fields\": [], \"required_missing\": [\"birth_date\", \"sex\"], \"next_question\": {\"field\": \"birth_date\", \"text\": \"你的出生日期是哪一天？请填写完整年月日。\", \"options\": [\"不知道\", \"跳过\"], \"allow_free_text\": true, \"can_skip\": true}, \"extraction\": null, \"requires_user_confirmation\": true, \"auto_submit\": false, \"persisted\": false, \"backend_validation_required\": true, \"error_code\": \"\", \"error\": null}"}, "execution_id": "SYNTHETIC-PLATFORM-EXECUTION-001"}}

```

- `message`、`node_finished`、`workflow_node_message`等均不是最终可展示结果；忽略中间模型正文和推理内容。
- `workflow_finished`的 `status.desc`须为`succeeded`，`waiting`不当成功；其状态数字与节点级数字不同，不复用业务 `code==0` 判据。
- 遇到 `error/exception`、失败终态、意外`node_wait`、超时、断流、缺少终态、正文空白或JSON无法解析，按本节失败规则处理。本版三条任务都不依赖平台暂停等待用户回复。
- `end`只表示流结束。HTTP 200或`end`不证明内部业务成功；即使终态成功也要验证 `schema_version/workflow_version`、关联ID、字段类型、内部 `status` 和后端闸门。
- 不从任意中间节点或任意层级递归寻找“看起来像结果”的JSON。实际渠道包装如有不同，先保存脱敏合成终态样本，明确新增一个适配分支并回归，不能猜测或静默兼容。[官方响应事件说明](https://support.huaweicloud.com/api-agentarts/agentarts_07_0056.html)

后端重新生成第5.11节的业务SSE事件或普通 `ApiResponse`。不要直接转发AgentArts事件，也不要在日志记录API Key、Authorization或完整健康原文。

#### 16.2.4 Python联调示例：私有请求头由调用方注入

下面示例把鉴权加载与凭据拼装移出代码，通过 `runtime_headers` 参数接收后端可信模块提供的请求头。缺少该参数不能调用；它不能来自患者浏览器或用户消息。本示例不修改运行时认证配置。

示例使用 `httpx`。当前项目只在开发依赖中有它，可用于联调；正式落地客户端时按项目规范执行 `uv add httpx` 声明运行时依赖。本次仅更新文档，没有安装依赖或修改后端业务实现。

```python
from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from uuid import uuid4

import httpx


async def invoke_workflow(
    client: httpx.AsyncClient,
    url: str,
    business_request: dict[str, object],
    runtime_headers: Mapping[str, str],
    platform_session_id: str,
    expected_schema: str,
    total_seconds: float,
) -> dict[str, object]:
    if not runtime_headers:
        raise ValueError("必须由后端传入私有运行时请求头")
    if total_seconds <= 0:
        raise ValueError("总超时时间必须为正数")
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-Invoke-Mode": "published",
        "x-hw-agentarts-session-id": platform_session_id,
        "X-Request-Id": str(uuid4()),
    }
    headers.update(runtime_headers)
    payload = {
        "inputs": {
            "request_json": json.dumps(
                business_request, ensure_ascii=False, allow_nan=False
            )
        }
    }
    async with asyncio.timeout(total_seconds):
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()
            data_lines: list[str] = []
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip(" "))
                    continue
                if line or not data_lines:
                    continue
                event = json.loads("\n".join(data_lines))
                data_lines.clear()
                if not isinstance(event, dict):
                    raise ValueError("平台事件结构不符合约定")
                kind = event.get("event")
                if kind in {"error", "exception", "node_wait", "end"}:
                    raise RuntimeError("平台未返回可用的成功终态")
                if kind != "workflow_finished":
                    continue
                data = event.get("data")
                if not isinstance(data, dict):
                    raise ValueError("平台终态缺少data对象")
                status = data.get("status")
                if not isinstance(status, dict) or status.get("desc") != "succeeded":
                    raise RuntimeError("平台执行未成功完成")
                outputs = data.get("outputs")
                if not isinstance(outputs, dict):
                    raise ValueError("平台终态缺少outputs对象")
                content = outputs.get("responseContent")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("平台最终业务正文为空")
                result = json.loads(content)
                if not isinstance(result, dict) or result.get("schema_version") != expected_schema:
                    raise ValueError("工作流业务协议不匹配")
                if result.get("request_id") != business_request.get("request_id"):
                    raise ValueError("工作流请求关联不匹配")
                return result
    raise RuntimeError("响应流结束但未收到成功终态")
```

调用参数按工作流选择：

| 工作流 | url来源 | business_request来源 | expected_schema | total_seconds |
| --- | --- | --- | --- | --- |
| Profile | 16.1的Profile地址 | 16.4或`profile-start.request.json` | `clear-complaint.profile-intake.workflow.v1` | 建议30 |
| Followup | 16.1的Followup地址 | 16.5或`followup-supplement.request.json` | `clear-complaint.followup-supplement.workflow.v1` | 最多8，不重试 |
| Triage | 16.1的Triage地址 | 16.3或`triage-generate.request.json` | `clear-complaint.triage.workflow.v1` | 建议最多50，整体业务仍限60 |

- `client`由后端统一管理；`runtime_headers`由独立私有凭据模块按工作流生成；`platform_session_id`由后端保存，不写死截图值。
- 只传业务对象，函数内部自动包装 `inputs.request_json`，不能再传整个 `*.http.json`，否则会重复包装。
- 示例读取完整SSE数据帧，并返回内部结果；`request_id`应由后端为每次逻辑请求提供。真实渠道包装若不一致，应核实后显式修改适配器。
- 返回值仍需后端检查已部署版本、业务ID、内部状态、受控目录、引用和最终模板。不能因为函数返回对象就直接进入 `ready`，也不能把对象直接返回患者。
- HTTP错误、平台错误、解析错误和总超时由调用方按16.6处理。Followup失败必须保留已计算的第一层建议，不能让随访主流程失败。

### 16.3 Triage-Workflow-MainFlow

用途：后端完成归一化、固定字段澄清和红旗检查后，调用本工作流检索资料、生成结构化草稿并做本轮工程校验。前端继续使用第 5 节的业务接口，不直接调用平台。

本节依据本地导出 `workflow_Triage-Workflow-MainFlow-IO-GenerationFix_20261121.jsonl` 及对应代码核对：输入协议为 `clear-complaint.triage.request.v1`，输出协议为 `clear-complaint.triage.workflow.v1`，工作流版本为 `2026-11-21.mainflow-io.3`。这些是本地契约基线；实际发布版本需联调时核对返回的 `workflow_version`，本文不表示已验证云端部署内容。

#### 16.3.1 业务输入 `request_json`

平台开始节点的唯一业务输入是 `request_json`，类型为 **String**，其值为下表对象序列化后的 JSON 文本。原生 `query` 不参与本版处理。下文代码块展示解码后的业务对象，不能将这个对象直接替代平台外层请求体；平台外层封装见本章公共调用约定。

| 字段 | 必填 | 类型与约定 |
| --- | --- | --- |
| `schema_version` | 是 | 固定 `clear-complaint.triage.request.v1` |
| `episode_id` | 是 | 非空字符串，最多 100 字符；后端数字 ID 转字符串 |
| `request_id` | 否，建议传 | 字符串，最多 100 字符；同一逻辑调用的网络重试复用，新一轮调用使用可区分的标识；不替代后端幂等控制 |
| `episode_status` | 是 | 固定 `generating`；其他状态不进入生成 |
| `complaint_text` | 是 | 原始主诉，1–500 字符；补充后仍保留原文，不用新增回答覆盖 |
| `normalized` | 是 | 下表七个字段组成的对象；`symptom` 必须有已知值，不接受其他字段名 |
| `profile_snapshot` | 是 | 已确认档案快照；至少有后端计算的整数 `age`（0–150）、`sex` 和非 null 的 `allergies`；未知按下文显式编码 |
| `clarification` | 是 | `{round, round_limit, skipped}`；`round` 为整数 0–5，`round_limit` 固定 5，`skipped` 为 Boolean |
| `red_flags` | 是 | `{checked, version, matched_rule_ids}`；实际完成后端检查后才传 `checked=true`；本地规则快照 `version=1`，编号必须属于同版本受控表且不重复 |
| `self_attribution` | 否 | 字符串或字符串数组；单独保存，不作为已确认症状，也不进入本版生成模型 |
| `vitals_snapshot` | 否 | 对象，未提供用 `{}`；不进入本版生成模型，不参与定档 |
| `env` | 否 | 对象，取不到环境信息用 `{}`；公共详情中的 null 在适配时转 `{}`，不进入本版生成模型 |

`request_json` 文本最多 64,000 字符，必须是 JSON 对象；未知顶层字段、重复 JSON 键、非有限数值会被拒绝。不要传旧版 `profile_json`、`structured_facts_json`、`history_summary` 或 `next_state_json`。

公共 API 的 `normalized` 与平台 `normalized` 字段名不同，必须由后端适配；平台字段接受字符串、字符串数组或 null，未答也可省略。字符串数组最多 20 项。

| 公共 API／后端字段 | 平台字段 | 含义 |
| --- | --- | --- |
| `symptom` | `symptom` | 主要症状，必须有已知值 |
| `onset_at` | `onset` | 起病时间，可为用户原有的自然语言时间 |
| `duration_text` | `duration` | 持续时间 |
| `site` | `location` | 部位 |
| `nature` | `character` | 性质 |
| `associated` | `associated_symptoms` | 伴随症状，明确否认的表现也按事实保留 |
| `medications_text` | `medication` | 本次已用药情况 |

`clarification_request.question_fields`、`missing_fields`、`unknown_fields` 使用平台字段名；转成第 2.12 节的问题卡时按上表反向映射。不能直接用平台字段名作为第 5.2 节的公开 `answers[].field`。

档案适配约定：

- `Profile.age_years` 映射为 `profile_snapshot.age`，由后端根据出生日期计算，不接受前端任意指定。`sex` 使用 `male/female/undisclosed`。
- 未确认、明确不知道或跳过的过敏史传 `allergies:["unknown"]`；用户明确确认无过敏史时可传 `allergies:[]`。平台不接受过敏史缺项、null 或空白字符串。
- 公共档案仍按第 2.3 节仅以 `birth_date/sex` 判断必填完成；无需为适配本工作流新增公共必填项。未提供过敏史时使用上述未知编码，不能补成“无过敏史”。
- 第 6.3 节中 `[]` 也可表达清空，不能仅凭数组为空推断用户已确认无过敏；后端按已保存的确认信息判断，无确认依据时传 `["unknown"]`。
- 未确认基础病史建议传 `conditions:["unknown"]`，明确确认无基础病时传 `conditions:[]`。直接传 null 虽会被当前代码转换为空数组，但会丢失“未知”语义。
- `condition_note`、`allergy_note` 为 null 时转 `""`；直接传 null 会被当前校验拒绝。两字段最多 200 字符。
- 本版进入生成模型的档案白名单仅有 `age/sex/conditions/condition_note/allergies/allergy_note`。姓名、出生日期、原始主诉、自我归因、天气和体征不进入模型提示词。

完整合成业务请求如下。仅用于软件联调；其中 `red_flags.checked=true` 模拟后端已执行规则，真实请求必须来自实际检查结果，不能让前端自行填写或固定写死。

```json
{
  "schema_version": "clear-complaint.triage.request.v1",
  "episode_id": "SYNTHETIC-TRIAGE-20261121-001",
  "request_id": "SYNTHETIC-REQUEST-001",
  "episode_status": "generating",
  "complaint_text": "【虚构试运行】我28岁，女性，三天前早晨开始流鼻涕，持续三天。主要在鼻部，是清水样鼻涕，程度较轻。偶尔打喷嚏，除此之外没有其他不适。最近没有服用药物，没有已知过敏史。",
  "normalized": {
    "symptom": "流鼻涕",
    "onset": "三天前早晨",
    "duration": "持续三天",
    "location": "鼻部",
    "character": "清水样鼻涕，程度较轻",
    "associated_symptoms": [
      "偶尔打喷嚏",
      "没有其他不适"
    ],
    "medication": "最近没有服用药物"
  },
  "self_attribution": [],
  "profile_snapshot": {
    "age": 28,
    "sex": "female",
    "conditions": [],
    "condition_note": "",
    "allergies": [
      "无已知过敏史"
    ],
    "allergy_note": ""
  },
  "vitals_snapshot": {},
  "env": {},
  "clarification": {
    "round": 0,
    "round_limit": 5,
    "skipped": false
  },
  "red_flags": {
    "checked": true,
    "version": 1,
    "matched_rule_ids": []
  }
}
```

#### 16.3.2 内部输出与公开 `Result` 映射

工作流返回完整的内部结果 JSON 文本。其 `status` 与公开 `episode.status` 不是同一个枚举，平台完成事件也不等于业务生成成功。后端应读取并校验 `schema_version/workflow_version/episode_id/request_id/status`，再处理结果。

| 内部字段 | 后端处理／公开字段 |
| --- | --- |
| `draft.triage` | 仅 `emergency/clinic/self_observe`；最终规则和闸门确认后写入 `Result.triage`，不直接透传 |
| `draft.department_primary`、`draft.department_secondary` | 核对同版本 17 科受控表；备选可为 null；急诊档首推必须为急诊科 |
| `draft.triage_evidence_idx`、`draft.department_evidence_idx` | 指向本轮 `output_list` 的依据下标；属于内部审计数据，不直接显示给患者 |
| `draft.conditions[]` | 每项仅有 `name/evidence[]`；后端再次核对受控名称和引用，写入 `Result.conditions` |
| `conditions[].evidence[]` | 含 `evidence_idx/doc_title/section/quote/quote_truncated`；公开 Evidence 取标题、章节与通过核验的摘录，内部保留原索引和截断标记 |
| `output_list` | 本轮证据池，条目为 `evidence_idx/document_name/subtitle/content`；保持原位置索引，不能跨调用复用或过滤后重编号 |
| `normalized` | 回传平台字段名；按适配表转回公开字段名，不替代后端原始回答和事实快照 |
| `clarification`、`clarification_request` | 追问状态回显及下一轮字段请求；问题文本、选项与用户回答落库由后端负责 |
| `missing_fields/unknown_fields/information_incomplete` | 记录信息完整性，不把明确未知或未答当成阴性事实 |
| `rule_result` | 防御性红旗短路结果；普通路径为 null，已确认急诊不能被通用兜底降级 |
| `needs_backend_fallback` | 提示后端组装保守结果；不能把 null 草稿当作正常草稿展示 |
| `backend_validation_required` | 固定 true，平台通过后仍须后端最终核验 |
| `platform_degraded` | 仅描述平台层工程降级，不直接等于公开 `Gate.degraded/fallback` |
| `gate_actions` | 记录候选删除、引用校验、截断及模型／知识检索调用情况，后端另行记录最终可展示结果的动作 |
| `controlled_versions` | 本地快照 `departments/vocab/red_flags` 均为整数 1；版本不匹配先停止正常采用草稿 |
| `error_code/error` | 内部原因与 `{code,message,retryable}`；按下表处理，用户文案仍使用后端模板 |

`triage_label`、`urgency_note`、`prep.bring/describe/go_now`、免责声明和档案摘要由后端模板生成；工作流草稿不提供这些可直接展示的自由文本。受控词表以实际快照为准，例如本地快照包含“上呼吸道感染”，不能假定其他近义名称均合法，也不能在不核验的情况下改名。

证据处理约定：

- 可用检索条目必须有非空真实来源标题和正文；不能给无标题的内容补一个泛名来通过校验。当前输出池不包含 URL、原知识库 ID 或 score，如后端需要这些溯源信息，应另行保存可靠的来源映射。
- 每条引用的 `quote` 必须逐字出现在对应 `evidence_idx` 的本轮 `content` 中。核验通过后才截取最多 120 字符；超长时返回 `quote_truncated=true`。
- 省略号只在后端展示时追加，不写入待核验的摘录。内部保留本轮原片段及截断标记，便于复核。
- 任一引用不合规时，当前平台闸门会剔除整个候选。候选可少于 3 条，全部剔除时也可为空；不得为凑数量添加疾病或编造引用。
- `gate_actions.citation_passed` 是平台逐条校验的通过计数；一个随后被剔除的候选也可能贡献通过数，因此不等于最终展示引用条数，不能直接用作公开 `citations_verified`。
- 逐字命中只证明引用来自原文，不能代替医学语义、适用人群和结论充分性核验。

#### 16.3.3 状态、降级与错误

| 内部 `status`／原因 | 后端动作 |
| --- | --- |
| `needs_clarification` | 读取待问字段，反向映射后用固定模板下发问题卡；业务进入／保持 `clarifying`；本次平台调用已经结束，不是在平台等待回复 |
| `draft_ready` | 本层草稿工程校验通过；后端最终核验、模板渲染后才能进入公开 `ready` |
| `insufficient_evidence`、`NO_RETRIEVAL_EVIDENCE` | 本轮无可用来源，通常 `draft=null`、`needs_backend_fallback=true`；保留已收集信息并按第 13 节保守兜底，不要求患者重答已知背景，不推断为自我观察 |
| `red_flag` | 采用已确认急诊规则结果，跳过普通知识和模型路径；不得被门诊兜底覆盖 |
| `failed` 且 `INVALID_REQUEST/400` | 修正序列化、字段名、类型或版本；属于调用问题，不伪装为正常草稿 |
| `failed` 且 `EMPTY_COMPLAINT/2001` 或 `COMPLAINT_TOO_LONG/2002` | 按公开参数错误处理；不进入模型 |
| `failed` 且 `EPISODE_STATE_NOT_ALLOWED/2005` | 拒绝当前状态下的生成，不将已完成问诊强行改成 `generating` |
| `failed` 且 `EMPTY_MODEL_OUTPUT/4004` | 模型未返回正文，保留本轮证据和失败信息，按既有重试／兜底规则处理 |
| `failed` 且 `INVALID_RETRIEVAL_OUTPUT/4004` 或 `INVALID_DRAFT/4004` | 本轮检索输出或草稿未通过校验，按生成失败处理；不展示被拒绝原文 |
| HTTP 错误、平台节点异常、超时或断流，没有完整内部结果 | 由后端客户端识别并按第 12 节的 4001/4002/4003 等处理；不能依赖工作流在失联时返回兜底 |

`NO_RETRIEVAL_EVIDENCE` 可以伴随 `error=null`，因此不能只检查 `error` 或平台 HTTP 200。`needs_backend_fallback` 为 false 的请求错误先修正调用；有效生成链失败才按业务规则组装保守结果。

`platform_degraded=true` 可能仅表示删除了某些不合规候选；如果最终仍采用合规草稿且未走兜底模板，不能因此直接设置公开 `Gate.degraded/fallback=true`。公开标记按第 5.6 节是否真正使用兜底模板判定。引用全被剔除仅使 `conditions=[]`，也不单独构成公开降级；整体草稿不可用或无证据后采用兜底模板时才标记降级。

后端红旗规则始终先运行，结果优先级高于模型建议。任何模型异常、证据不足、普通门诊兜底或后续补充处理均不得将已确认的急诊降为门诊或自我观察；体征不参与本项目定档，不能以体征看似正常否定已命中的红旗。

#### 16.3.4 轮次、补充与新问诊边界

五类关键字段是 `onset/duration/location/character/associated_symptoms`。存在未答关键缺项、未整体跳过且已下发轮次不到 5 时，工作流只返回下一轮待问字段。`medication` 缺失时随关键缺项附加到待问字段，单独缺用药不阻断生成；每轮最多 5 问。

后端可直接检查字段并下发固定问题卡，无需每轮都调用平台。已知字段不重复问；`unknown`、不知道、不清楚、不确定、未知、未提供、不详、跳过视为明确未知，不再作为未答问题。关键字段未知仍保留 `information_incomplete=true`。达到第 5 轮或 `skipped=true` 后不再阻断生成，最终证据或草稿不足时由后端兜底。

`clarification.round` 只统计实际下发给用户的问题轮次；网络重试不增加，不能因新 HTTP 请求清零。单字段跳过将对应值记为 `unknown`；整体跳过后续澄清才设 `skipped=true`。

| 后端问诊状态 | 用户补充处理 |
| --- | --- |
| `clarifying` | 接受本轮合法字段回答，保存原话并确定性合并字段；补充后重新执行红旗规则；继续澄清或进入生成 |
| `generating` | 不并发追加第二份生成任务，不覆盖正在执行的快照；后端处理幂等与状态冲突，保留用户已填内容 |
| `failed` | 使用第 5.4 节重试流程，复用原问诊与已保存回答，不清空已收集信息 |
| `ready` | 原结果用于展示与受限问答；需要重新评估的新情况使用新问诊入口，可预填原主诉和新增情况供用户确认，不覆盖旧草稿 |
| `saved/expired` | 不恢复原问诊生成，按业务规则创建新问诊；`saved` 为终态 |

同一次生成前的补充保持 `episode_id`，每次调用提交合并后的完整 `normalized/profile_snapshot/clarification` 快照，不只传一句“三天了”。原始主诉逐字保留，补充回答另行保存；明确更正由后端核对并更新，不能机械拼接矛盾值。

工作流没有跨调用记忆，不返回旧版 `next_state_json`。后端负责身份归属、已答字段、问题轮次、请求幂等、当前状态、草稿、证据与核验记录的持久化和恢复。第 5.10 节结果页受限问答只使用已核验引用及模板，不重新检索、不调用本工作流、不改定档；新症状需重新评估时走新问诊。

### 16.4 Profile-Intake-Workflow

负责通过对话逐项采集档案信息，输出待确认的临时表单。用户确认保存后，仍由后端调用第 6.3 节的档案更新业务；本工作流不会自动创建正式档案、保存用药或创建提醒。调用地址、鉴权及平台封装使用 16.1–16.2 的公共约定。

#### 16.4.1 平台输入契约

唯一业务入参为 `request_json: String`。下表描述该字符串内的 JSON 对象，不是 HTTP 最外层请求体。原生 `query` 不作为用户本轮回答。

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `schema_version` | String | 固定 `clear-complaint.profile-intake.request.v1` |
| `session_id` | String | 必填，1–100 字符；后端生成的档案采集会话标识；不替代用户身份或业务归属校验 |
| `request_id` | String | 工作流允许省略或空，最长 100 字符；接入方每次业务操作必须提供，以便关联日志和幂等 |
| `action` | String | `start` 开始、`answer` 回答、`skip` 跳过当前字段 |
| `as_of_date` | String | 必填，`yyyy-MM-dd`；后端按 `Asia/Shanghai` 生成，用于日期校验 |
| `form_snapshot` | Object | 当前可信临时表单；只包含 `name/birth_date/sex/city_code/city_name/conditions/condition_note/allergies/allergy_note` |
| `medication_drafts` | Array 或 null | 独立的临时长期用药记录；每项只能包含 `name/dosage_text/frequency_text`，不放入 `form_snapshot` |
| `active_field` | String 或 null | `answer/skip` 时取上次 `next_question.field`；首次 `start` 可为 null |
| `user_input` | String | 必填，最长 2000 字符；`answer` 时不得为空；`start/skip` 可为空 |
| `skipped_fields` | Array<String> | 已跳过字段；接续时保留，不再自动追问 |
| `unknown_fields` | Array<String> | 用户明确不知道的字段；与 `skipped_fields` 不重叠，不转成阴性事实 |
| `required_fields` | Array<String> | **后端每次显式传 `["birth_date", "sex"]`，与第 2.3、6 节正式档案口径一致** |

工作流内部缺省 `required_fields` 还包含 `allergies`，因此本项目不能省略该参数。过敏史仍会按采集顺序询问，但不据此新增正式档案必填项。公共 `Profile.required_missing` 仍由后端按照 `birth_date/sex` 计算，不直接复制平台内部字段。

采集顺序固定为 `birth_date → sex → allergies → conditions → long_term_medication → name → city_name`。已填写、已跳过或明确未知的字段不会自动再问。只填写完必填项后，用户也可以切回表单确认，不要求问完所有可选项。

输入转换要求：

- `GET /api/profile` 的公共对象需先挑选上表允许的字段；不能把包含 `age_years/required_missing/updated_at` 的对象整份传入。
- `null` 或未提供表示尚未知晓；`conditions=[]`、`allergies=[]`、`medication_drafts=[]` 分别表示用户明确没有相应情况，不能用空数组冒充未知。
- 生日不得早于 `1900-01-01` 或晚于 `as_of_date`；只从原文提取完整年月日，不从年龄推算。性别仅为 `male/female/undisclosed`，不从姓名推断。
- 基础病、过敏数组最多 10 项，每项最长 20 字；备注最长 200 字。用药最多 10 项，名称 1–40 字，用量、频次各最长 40 字并保留原文，不推算剂量或疗程。
- 城市名由原文提取后，工作流会清空旧 `city_code`。前后端城市选择器核实行政区划后，才能按第 6.3 节成对提交 `city_code/city_name`。
- `skipped_fields/unknown_fields` 只允许上述七个采集字段，不能重复；已有确定值的字段不能同时标记为跳过或未知。

#### 16.4.2 完整合成请求

以下是软件联调样例，JSON 对象需按 16.2 节序列化到平台的 `request_json` 字符串，不表示已经完成线上联调。

首次开始：

```json
{
  "schema_version": "clear-complaint.profile-intake.request.v1",
  "session_id": "SYNTHETIC-PROFILE-001",
  "request_id": "SYNTHETIC-INTAKE-001",
  "action": "start",
  "as_of_date": "2026-11-21",
  "form_snapshot": {},
  "medication_drafts": null,
  "active_field": null,
  "user_input": "",
  "skipped_fields": [],
  "unknown_fields": [],
  "required_fields": [
    "birth_date",
    "sex"
  ]
}
```

上次问题为 `birth_date` 时提交回答：

```json
{
  "schema_version": "clear-complaint.profile-intake.request.v1",
  "session_id": "SYNTHETIC-PROFILE-001",
  "request_id": "SYNTHETIC-INTAKE-002",
  "action": "answer",
  "as_of_date": "2026-11-21",
  "form_snapshot": {
    "name": null,
    "birth_date": null,
    "sex": null,
    "city_code": null,
    "city_name": null,
    "conditions": null,
    "condition_note": null,
    "allergies": null,
    "allergy_note": null
  },
  "medication_drafts": null,
  "active_field": "birth_date",
  "user_input": "我是1998年5月20日出生的。",
  "skipped_fields": [],
  "unknown_fields": [],
  "required_fields": [
    "birth_date",
    "sex"
  ]
}
```

下一次调用不能继续使用空快照。后端从上次可信返回值组装本次状态：

| 下次请求字段 | 取值 |
| --- | --- |
| `form_snapshot` | 上次 `form_draft` |
| `medication_drafts` | 上次 `medication_drafts` |
| `skipped_fields/unknown_fields` | 上次同名字段 |
| `active_field` | 上次 `next_question.field` |
| `user_input` | 本次用户原始回答 |
| `action` | 回答为 `answer`；点击跳过为 `skip` |
| `session_id` | 保持同一采集会话 |
| `request_id` | 新操作使用新值；同一操作重试沿用原值 |
| `required_fields` | 始终显式传 `["birth_date", "sex"]` |

关联 ID 和平台会话 ID 不能替代上述完整状态。后端需校验会话归属、当前待答字段及并发版本，并对重复请求只应用一次变化；不得把前端上传的快照视为可信状态。

#### 16.4.3 返回、状态与确认保存

业务结果 `schema_version=clear-complaint.profile-intake.workflow.v1`，当前 `workflow_version=2026-11-21.profile-intake.1`。先按 16.2 节解析平台最终结果，再处理下列字段。

| 字段 | 含义 |
| --- | --- |
| `status` | 下表所列的采集状态，不是公共档案的保存状态 |
| `form_draft` | 完整临时表单；不能直接当正式档案已保存 |
| `form_patch` | 本次核验通过的字段变化；不含长期用药；城市可能同时清空编码 |
| `medication_drafts` | 临时长期用药数组；不自动确定 `kind/started_on/ended_on` 或提醒时间 |
| `required_missing` | 本次两项必填策略下仍缺的字段；跳过或未知的必填项仍可能出现在这里 |
| `next_question` | 单个 `{field,text,options,allow_free_text,can_skip}` 对象或 null；使用已验证的固定问题 |
| `extraction` | 本轮 `{field,state,value,quote}` 或 null；是原文支持的待确认信息，不是正式医疗事实认证 |
| `requires_user_confirmation` | 固定 true |
| `auto_submit/persisted` | 固定 false |
| `backend_validation_required` | 固定 true |
| `error_code/error` | 内部诊断；不直接当第 12 节公共业务错误码，不原样展示产品技术错误 |

| 内部状态 | 后端与前端处理 |
| --- | --- |
| `needs_answer` | 保存临时表单及状态，展示一个 `next_question`，允许回答、跳过或切表单 |
| `ready_for_confirmation` | 展示完整可编辑表单和确认按钮；尚未保存，不自动提交 |
| `review_required` | 无剩余可问字段，但必填仍缺；切表单补齐，不无限重复追问 |
| `retry_required` | 保留旧临时表单及当前问题，让用户重新回答或切表单 |
| `failed` | 请求或状态无效等内部问题；保留后端原临时状态，记录诊断并返回既定产品错误文案 |

下面是已有离线样例中的“表单完整、等待确认”结果，仅演示结果形状；它与上面只回答生日的请求不是同一轮结果：

```json
{
  "schema_version": "clear-complaint.profile-intake.workflow.v1",
  "workflow_version": "2026-11-21.profile-intake.1",
  "session_id": "SYNTHETIC-PROFILE-001",
  "request_id": "SYNTHETIC-INTAKE-COMPLETE",
  "status": "ready_for_confirmation",
  "form_draft": {
    "name": "演示用户",
    "birth_date": "1998-05-20",
    "sex": "female",
    "city_code": "310100",
    "city_name": "上海市",
    "conditions": [],
    "condition_note": "",
    "allergies": [],
    "allergy_note": ""
  },
  "medication_drafts": [],
  "form_patch": {},
  "skipped_fields": [],
  "unknown_fields": [],
  "required_missing": [],
  "next_question": null,
  "extraction": null,
  "requires_user_confirmation": true,
  "auto_submit": false,
  "persisted": false,
  "backend_validation_required": true,
  "error_code": "",
  "error": null
}
```

确认保存仍遵循现有业务 API：

1. 前端显示完整表单，允许用户核对和修改。模型提取或逐字核验通过，均不替代用户确认。
2. 用户明确点击保存后，按第 6.3 节提交 `PUT /api/profile`；后端重新校验字段并计算年龄。
3. 长期用药经用户确认后，单独按第 8 节用药接口保存。缺少的 `kind/started_on` 等字段由表单补齐，不能由工作流补猜；用药提醒仍须走用药计划接口。
4. 已保存的确定信息再映射为 Triage 的 `profile_snapshot`；未确认的临时表单不能混入正式问诊快照。过敏史跳过或未知时，在 Triage 适配层使用 `allergies: ["unknown"]`，不能改写为 `[]` 或“无过敏”。该标记不是要写入公共 Profile 的病名数组。

平台无响应、最终事件缺失、空模型正文或提取失败时，不得清空已有临时表单，也不得显示保存成功。对原本已填写的字段进行更正时，用户切回表单编辑，避免迟到的旧回答覆盖新值。

#### 16.4.4 公开档案对话入口的缺口与最小建议（待实现）

原第 6 节只定义 `GET/PUT /api/profile` 等正式档案接口，**没有定义档案对话采集的公开 HTTP 入口**。本节平台调用契约不表示后端已经完成该入口。

为承接前端对话，可新增下面一个最小接口，状态存储、鉴权、幂等及错误映射仍需后端实现并完成联调：

`POST /api/profile/intake`（建议路径，待实现；需要用户登录）

前端只发送：

```json
{
  "action": "start",
  "session_id": null,
  "request_id": "SYNTHETIC-PUBLIC-INTAKE-001",
  "user_input": ""
}
```

- `action` 为 `start/answer/skip`。首次 `start` 不携带现有会话，`session_id=null`，后端生成并返回会话标识；回答或跳过必须带同一会话标识。
- `request_id` 为本次操作幂等标识；同一用户、同一会话、同一标识与相同请求体只应用一次；相同标识配不同正文拒绝为状态冲突。
- `user_input` 是当前回答，`answer` 时非空；开始或跳过可为空。
- 前端不发送 `active_field/form_snapshot/required_fields` 等可信状态；后端加载会话并生成 16.4.1 的完整平台请求。
- 建议成功时仍用 `{code:0,message:"ok",data:{...}}`，`data` 只包含经后端校验的 `session_id/request_id/status/form_draft/medication_drafts/required_missing/next_question/requires_user_confirmation`；内部错误、模型原文及凭证不透传。
- 本接口仅更新临时草稿，确认保存继续使用 `PUT /api/profile`，不把对话入口当自动保存接口。

### 16.5 Followup-Supplement-Workflow

负责第 10.2 节随访的第二层补充，只从后端批准的目录和原准备清单中选择观察项、准备项下标和一个可选问题。随访第一层档位与文案仍由后端固定规则决定，平台不重算、不覆盖。

#### 16.5.1 调用位置与适用条件

前端仍提交现有 `POST /api/reminders/{id}/respond`，后端依次处理：校验提醒归属及状态 → 校验原始回答 → 执行红旗及八条优先级规则 → 判断第二层是否适用 → 可选调用平台 → 校验并交付结果。

同时满足以下条件才调用第二层：

- 原问诊 `original_result.triage=self_observe`；原问诊为 `clinic` 时走复查提醒，为 `emergency` 时不创建该类随访。
- 本次后端第一层 `first_layer.level=clinic`。
- `first_layer.reason` 为 `not_relieved/worsened/new_symptom/worsened_after_visit` 之一。

第一层为 `emergency/closed/self_observe` 时，直接交付后端结果，不调用模型。工作流还有防御性不适用分支，但后端不能依赖它代替调用前判断。随访只产生随访记录，不新建问诊；需要重新问诊时由用户进入新问诊流程。

#### 16.5.2 平台输入契约

唯一业务入参为 `request_json: String`；下表是字符串内的对象，使用 16.1–16.2 的地址、鉴权和序列化约定。

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `schema_version` | String | 固定 `clear-complaint.followup-supplement.request.v1` |
| `episode_id/followup_id` | String | 必填，各 1–100 字符；后端可信业务 ID。公共数值 ID 在适配层明确转字符串 |
| `request_id` | String | 工作流允许省略或空，最长 100 字符；后端接入必须提供以便关联及去重 |
| `first_layer` | Object | `{level,reason,text?}`；后端已计算结果，text 最长 2000 字符；平台不能改写 |
| `answers` | Object | 必须含 `relieved/visited/new_symptom`；分别为 `yes/no/worse`、`yes/no`、`yes/no` |
| `note` | String | 可选，最长 200 字；用户随访原话，红旗判定已由后端执行 |
| `normalized_snapshot` | Object | 可选，原问诊七类规范化症状字段；仅传允许的字段 |
| `original_result` | Object | 允许补充时必需，只包含 `{triage,department_primary,prep}`，不发送完整公共 Result |
| `catalogs` | Object | 允许补充时必需，`{version,watch_for:[{id,text}],questions:[{id,text}]}`；由后端维护和批准 |

第一层内部适配枚举如下；它们表示后端规则的既有结果，不让模型自由生成原因：

| `level` | 允许的 `reason` |
| --- | --- |
| `clinic` | `not_relieved/worsened/new_symptom/worsened_after_visit` |
| `emergency` | `red_flag` |
| `closed` | `closed_visited/closed_improved/closed_expired` |
| `self_observe` | `observe`，仅不适用分支 |

`normalized_snapshot` 与第 2.11 节公共归一化字段名称不同，后端必须显式转换，不能整份直接传入：

| 公共 `EpisodeDetail.normalized` | 平台 `normalized_snapshot` |
| --- | --- |
| `symptom` | `symptom` |
| `onset_at` | `onset` |
| `duration_text` | `duration` |
| `site` | `location` |
| `nature` | `character` |
| `associated` | `associated_symptoms` |
| `medications_text` | `medication` |

每个值只允许字符串、字符串数组或 null；字符串最长 2000 字符。多传 `onset_at/site` 等未约定键会导致请求校验失败。

受控目录要求：

- `catalogs.version` 必填，最长 100 字符；两组目录均需非空，每组最多 20 项。
- 条目 `id` 最长 100 字符，观察项 `text` 最长 100 字符，问题模板 `text` 最长 150 字符；编号与原文字面值均需唯一。
- 目录由后端维护并经内容批准，不让前端或模型随意新增，不由工作流临时生成医学词表。
- 观察项仅为可观察表现，不能夹带诊断、药名剂量、停换药或处置指令。工程文本拦截不能替代医学内容审核。
- 下面的合成目录只用于软件联调，不代表已经获得医学审核；正式环境必须替换为批准版本。

#### 16.5.3 完整合成请求

本例用于解释数据形状，不表示已完成线上调用：

```json
{
  "schema_version": "clear-complaint.followup-supplement.request.v1",
  "episode_id": "SYNTHETIC-EPISODE-001",
  "followup_id": "SYNTHETIC-FOLLOWUP-001",
  "request_id": "SYNTHETIC-FOLLOWUP-REQUEST-001",
  "first_layer": {
    "level": "clinic",
    "reason": "not_relieved",
    "text": "合成规则结论：门诊评估"
  },
  "answers": {
    "relieved": "no",
    "visited": "no",
    "new_symptom": "no"
  },
  "note": "软件合成用例：鼻部不适仍存在。",
  "normalized_snapshot": {
    "symptom": "鼻部不适",
    "duration": "三天"
  },
  "original_result": {
    "triage": "self_observe",
    "department_primary": "全科医学科",
    "prep": {
      "bring": [
        "携带已保存的不适记录"
      ],
      "describe": [
        "整理这次不适的开始时间",
        "记录与上次相比有哪些变化"
      ],
      "go_now": []
    }
  },
  "catalogs": {
    "version": "synthetic-demo.v1-not-clinically-validated",
    "watch_for": [
      {
        "id": "demo-obs-1",
        "text": "鼻部不适是否仍存在"
      },
      {
        "id": "demo-obs-2",
        "text": "日常活动是否受影响"
      }
    ],
    "questions": [
      {
        "id": "demo-question-1",
        "text": "这次不适对日常活动有什么影响？"
      }
    ]
  }
}
```

准备项编号固定按 `bring` 全部条目 → `describe` 全部条目 → `go_now` 全部条目平铺，全局下标从 0 开始。上述例子为：

| 全局下标 | 原位置 | 文本 |
| --- | --- | --- |
| 0 | `bring[0]` | 携带已保存的不适记录 |
| 1 | `describe[0]` | 整理这次不适的开始时间 |
| 2 | `describe[1]` | 记录与上次相比有哪些变化 |

每个数组内保持原顺序；来自不同位置的相同文本仍有各自下标。模型只能选择下标，不能改写原准备项。

#### 16.5.4 返回、校验与公开 API 映射

内部结果 `schema_version=clear-complaint.followup-supplement.workflow.v1`，当前 `workflow_version=2026-11-21.followup-supplement.1`。已有离线合成输出示例：

```json
{
  "schema_version": "clear-complaint.followup-supplement.workflow.v1",
  "workflow_version": "2026-11-21.followup-supplement.1",
  "episode_id": "SYNTHETIC-EPISODE-001",
  "followup_id": "SYNTHETIC-FOLLOWUP-001",
  "request_id": "SYNTHETIC-FOLLOWUP-REQUEST-001",
  "status": "supplement_ready",
  "supplement": {
    "watch_for": [
      "鼻部不适是否仍存在",
      "日常活动是否受影响"
    ],
    "prepare_idx": [
      0,
      2
    ],
    "next_question": "这次不适对日常活动有什么影响？"
  },
  "degraded": false,
  "error_code": "",
  "error": null,
  "first_layer": {
    "level": "clinic",
    "reason": "not_relieved",
    "text": "合成规则结论：门诊评估"
  },
  "prepare_candidates": [
    {
      "index": 0,
      "group": "bring",
      "source_index": 0,
      "text": "携带已保存的不适记录"
    },
    {
      "index": 1,
      "group": "describe",
      "source_index": 0,
      "text": "整理这次不适的开始时间"
    },
    {
      "index": 2,
      "group": "describe",
      "source_index": 1,
      "text": "记录与上次相比有哪些变化"
    }
  ],
  "backend_validation_required": true,
  "model_called": true
}
```

| 字段或状态 | 后端处理 |
| --- | --- |
| `status=supplement_ready` | 校验业务关联 ID、目录版本、观察项及问题来源、准备项编号，再映射 `supplement` |
| `status=not_applicable` | `supplement=null`，`model_called=false`；不算第二层降级 |
| `status=degraded/failed` | `supplement=null`；保留第一层，将原因和降级写入随访记录，不向用户暴露内部异常 |
| `supplement.watch_for` | 最多 4 项，字面内容只能来自本次批准目录；可以为空数组 |
| `supplement.prepare_idx` | 整数下标去重、去越界后必须有 2–4 项，并升序返回；否则整层补充为 null |
| `supplement.next_question` | 本次批准问题模板原文，或 null；不允许自由生成额外问题 |
| `prepare_candidates` | `{index,group,source_index,text}` 数组，用于核对准备项位置与原文；只在后端内部使用 |
| `first_layer` | 用于对照；必须与后端已计算值一致，绝不能用返回值替换后端可信结果 |
| `degraded/model_called/error_code/error` | 内部审计字段，不新增到公开 Supplement 对象 |
| `backend_validation_required` | 固定 true，平台核验不替代后端终检 |

公开接口继续沿用第 10.2 节：

- `data.status` 是提醒处理状态（如 `done`），不使用平台内部 `supplement_ready` 作为提醒状态。
- `data.advice` 始终由后端第一层规则产生；平台返回不改变原档位、原因、文案或就医时间窗。
- `data.supplement` 仅保留第 2.13 节既有的 `watch_for/prepare_idx/next_question` 三字段，或整体为 null。
- 后端按同一份原 `prep` 候选平铺顺序展开 `prepare_idx`，并遵循公共 API 的三字段结构。相同请求期间原准备清单不能被替换成另一版本。
- 第一层及原结果的风险提示按既有规则照常展示，不能因模型未选中某个 `go_now` 下标而隐藏。
- 随访答案、第一层结果、目录版本、平台业务关联 ID 及降级记录关联到同一条随访，不创建新问诊，不自动修改原问诊草稿。

#### 16.5.5 8 秒总预算与异常处理

后端必须执行第二层调用的 **8 秒总超时预算，不重试**。该预算应覆盖 HTTP 连接、等待平台流、解析最终结果及返回前必要检查；不能只设置模型节点的超时。

DSL 模型节点配置 6 秒、重试 0 次，用于留出其他步骤时间，但不能保证整条平台 HTTP 调用 8 秒内完成。因此后端还必须处理平台整体超时、网络中断、鉴权或额度错误、节点中断、缺少最终结果以及响应结构校验失败。

以上异常一律保留已计算的第一层，令 `supplement=null`，随访记录标记降级，公开响应仍按现有随访成功形状交付。不能依赖工作流在自身失联时返回降级 JSON，也不能为了补充层失败而重跑第一层或重复处理提醒。

本次文档约定了调用数据及责任分工，不表示后端平台客户端、目录审批、状态存储或公开接口已经实现；上线前仍需对三个实际运行时分别完成鉴权、终态解析和超时降级联调。

### 16.6 后端处理、超时与状态接续

#### 16.6.1 三类成功互不等价

| 层级 | 成功条件 | 不能由此推断的事 |
| --- | --- | --- |
| HTTP/平台执行 | 请求可达，工作流成功结束，有可解析终态 | 内部状态不一定是草稿已生成 |
| 工作流内部 | 与本任务相符的schema、版本、关联ID、内部状态及数据结构通过检查 | 不代表已保存、不代表可直接展示 |
| 清诉业务 | 后端完成归属、状态、字段/引用、目录、模板及持久化等校验 | 仍不把模型内容作为确定诊断 |

`backend_validation_required`必须为true。后端不信任浏览器提交的规则结论、证据、完整事实快照或第一层随访建议，只从自己的可信状态组装这些字段。

#### 16.6.2 错误映射与预算

| 情况 | Triage | Profile | Followup第二层 |
| --- | --- | --- | --- |
| HTTP连接失败、认证失败或平台运行错误 | 记录内部原因；有效生成任务按4001等保守兜底 | 保留临时草稿和当前问题，允许重试/切表单 | `supplement=null`，记录降级，第一层照常返回 |
| 超时/断流/缺少最终结果 | 按4002和现有兜底处理；不丢原始输入 | 不当作保存成功，不清空已填内容 | 总预算8秒，取消等待、不重试 |
| 429或额度不足 | 记录4003，执行已有保守兜底 | 给固定失败提示并保留草稿 | 主响应仍成功，第二层为空 |
| 输入错误、ID不符、版本不符 | 修正后端参数/部署；不得当正常草稿 | 保留草稿，不应用不可信patch | 保留后端第一层并记录问题 |
| 终态JSON不合规/空模型正文 | 按4004处理有效生成失败；平台可能给 `EMPTY_MODEL_OUTPUT` | 保留原表单，重答或表单核对 | 第二层为空，记录降级 |

- Triage整体遵守第5.11节60秒预算。建议为上游平台预留不超过50秒的总预算，留出最终闸门和模板时间；连接/读取超时以外还应有覆盖整个调用的总截止时间。
- Profile建议采用30秒总预算作为本次接入配置；这是新增建议值，失败保留临时表单，没有60秒内必须自动保存的业务含义。
- Followup第二层从发起调用到拿到并验证完整结果最多8秒，不重试。不能仅设置“每个读取分片8秒”，否则总时长可无限延长；超时取消上游等待，但不假定平台已停止计费或停止执行。
- Triage有效任务若已由后端产生合规兜底，按第12节输出业务 `result_section/done`，最终 `degraded=true`、`gate.fallback=true`。只有无法构成合法业务结果时才输出 `error`；不同时发 `done` 和 `error`，也不把平台草稿原文当兜底。
- 后端自身已命中红旗的急诊结果具有优先级，不能被普通“门诊/全科”兜底降级。
- Profile/Followup内部诊断码不是现有公开API的业务错误码。Profile新增公开入口的错误码需随路由一起落地；Followup第二层错误不改写主响应为4001–4004。

#### 16.6.3 补充、新轮次和幂等由后端判定

| 场景 | 后端动作 | 发送给平台的内容 |
| --- | --- | --- |
| 问诊 `clarifying` 收到本轮回答 | 保存原话、核对字段、更新完整规范化快照，重跑红旗和缺项检查 | 到生成阶段才调用Triage；发送完整快照，不只发“持续三小时” |
| 整体跳过或达到5轮 | 标记信息不完整，保留已有答案，合法进入生成 | `clarification.skipped=true`或`round=5` |
| 单字段明确未知 | 保存未知状态并停止重复询问该字段 | 对应值为`unknown`，不能改成“没有” |
| 问诊 `generating`收到重复请求 | 按第1.6节附着/回放，防止并发覆盖 | 不凭相同 `request_id`假定平台自动去重 |
| 问诊 `failed`重试 | 复用本问诊和已收集信息，按后端重试规则处理 | 完整原快照，不清空追问轮次 |
| 问诊 `ready/saved`后出现新健康情况 | 按当前主流程新建问诊，原结果保持可追溯 | 新 `episode_id`，用户确认后的新主诉和独立快照 |
| 结果页询问“为什么这样建议” | 走第5.10节受限问答，读本问诊已核验引用 | 不调用这三条工作流 |
| 档案采集继续回答 | 保持采集会话，保存临时表单、已跳过/未知字段和当前问题 | Profile完整临时快照和本轮原话 |
| 随访提交 | 按提醒归属和处理状态防重，先算第一层；仅适用时补第二层 | Followup的既有问诊快照和已批准目录 |

内部 `request_id`只用于关联逻辑请求；上游平台不提供本项目需要的业务幂等保证。后端需要保存请求状态，取消/超时后的迟到结果不得覆盖更新后的状态；必要时采用版本号或执行令牌校验。第1.6节的既有对外幂等头继续保留，不因这里出现了 `request_id`而删除。

### 16.7 交接包与联调验收

交接包的 `requests` 同时提供两种文件：

| 文件 | 用途 |
| --- | --- |
| `profile-start.request.json` / `.http.json` | 档案采集首轮：内层业务对象 / 可直接发送的HTTP Body |
| `profile-answer.request.json` / `.http.json` | 同一采集会话回答出生日期，仍需后端真实保存首轮状态 |
| `triage-generate.request.json` / `.http.json` | Triage完整合成请求，是否有草稿取决于实际知识库与模型 |
| `triage-clarify.request.json` / `.http.json` | 缺持续时长的防御性追问请求，预期 `needs_clarification` |
| `followup-supplement.request.json` / `.http.json` | Followup允许第二层的合成目录请求，仅用于软件联调 |

`*.request.json`用于平台手工试运行或由后端自行序列化；`*.http.json`用于HTTP调用。不要把后者完整粘进开始节点的 `request_json`，也不要把前者直接作为最外层Body发给平台。

上线前至少完成以下合成用例；本次只验证本地请求与DSL契约，不声明已通过下列云端验收：

1. 三个新URL分别使用对应的Key，收到预期schema/版本/业务关联ID。用错Key能受控失败，不把401发成患者登录过期。
2. 正常Profile首轮出现一个问题；回答后保留出生日期，进入下一字段；`ready_for_confirmation`后仍需用户确认。跳过或明确未知不能变成“无病史”。
3. Triage完整输入进入检索；无证据返回 `insufficient_evidence`并由后端兜底，不反复要求用户补背景。真实草稿还要过后端引用/词表/模板闸门。
4. Triage缺持续时间时返回字段请求；后端映射到 `duration_text`，回答后传完整新快照；重试不重复累计轮次。
5. 后端红旗测试直接走急诊，不调用模型；平台故障也不能降低急诊级别。
6. Followup正常结果只包含批准目录文本及原准备项下标；急诊/关闭态不调模型；目录缺失、越界、8秒超时均保留第一层并返回空补充。
7. 平台SSE跨网络分片、中文UTF-8截断、非成功终态、空正文与断流均能正确处理；中间模型内容不进入前端。
8. 同一请求重复提交、同一幂等键不同Body、迟到的旧结果和跨用户会话访问均有受控处理。

当前还需要后端负责人落地：平台客户端与终态解包、配置/密钥注入、两个方向的字段适配、请求幂等及超时、档案采集临时状态与公开入口、规则与受控目录、最终核验/模板及持久化。这些属于待实现清单，不因本文件有调用路径而视为完成。
