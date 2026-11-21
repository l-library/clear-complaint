# 阶段一实验

阶段一的研究工件：语料、病例、被测系统、实验记录与分析。设计与口径见 [docs/stage1.md](../docs/stage1.md)。

## 与后端的关系

本目录是独立的 uv 项目，**不 import `backend/` 的任何代码**，后端也不依赖它。阶段二需要这里的归一化、红旗、引用核验逻辑时，复制副本进 `backend/app/`，两处各自独立可运行。这样阶段一不会被后端的迁移与接口演改进度拖住，也不会污染后端的依赖与类型检查。

## 目录

| 目录 | 内容 | 入仓库 |
|---|---|---|
| `tools/` | 抓取与构建脚本 | 是 |
| `corpus/kb/` | 导出给平台知识库的文件集与 `kb_manifest.csv` | 是 |
| `corpus/` | 指南片段、冻结向量、候选词表、科室表、红旗清单 | 是 |
| `cases/` | 病例、五个变体、金标准、签核记录 | 是 |
| `harness/` | 归一化、红旗、检索、引用与模板校验、模型客户端 | 是 |
| `arms/` | 四个实验臂的提示词与开关快照 | 是 |
| `runs/` | 每次调用的原始响应与参数，只追加 | 是 |
| `analysis/` | 指标、bootstrap、`figures/` | 是（图） |
| `handoff/` | `constraints.md` 五条约束的规格与实测效应；`frozen_sample.jsonl` 100 条验收样本 | 是 |

语料、病例与 run 记录一律入仓库。证据不在仓库里就等于没有，所以不用 `.gitignore` 挡体积。

## 当前状态

语料已锁定九个病种域，51 份文件、1373 条条款，覆盖表在 `corpus/probe_ingested.md`。域的口径是病种而非症状，理由见 [docs/stage1.md](../docs/stage1.md) 的「语料」一节。

两轮的实测结论：

- `corpus/probe_report.md`：`gov.cn` 政策文件库只对上呼吸道、发热、腹泻、皮疹四个症状域给出充足片段，头痛为零。这是换源与改域口径的依据，报告留着做对照。
- `corpus/download_list.md`：`nhc.gov.cn` 上找到的 45 份诊疗类文件清单，覆盖的域多得多（脑血管病、急性冠脉综合征、房颤、心衰、慢阻肺、肥胖症、诺如、尼帕、埃博拉等）。

`nhc.gov.cn` 正文页有瑞数动态防护：真实 Chromium 预热拿到 cookie 后能取到 200 全文，但连续自动化请求会被升级拦截（412 → 400）。所以正文与附件改由人工下载到 `corpus/raw/`，分片与统计全部离线，不依赖反爬。

```bash
cd experiment
uv sync
uv run python -m tools.ingest --ocr        # 抽正文，扫描件走 PaddleOCR（需 PADDLEOCR_ACCESS_TOKEN）
uv run python -m tools.fetch_govcn         # 从政策文件库补齐传染病诊疗方案
uv run python -m tools.chunk               # 切片，产出 corpus/chunks.jsonl
uv run python -m tools.controlled          # 三张受控表，每条都要能在语料里指到原文
uv run python -m tools.embed               # 冻结向量，需 EMBED_API_KEY 或 MAAS_API_KEY
uv run python -m tools.build_kb            # 导出可上传平台知识库的 56 份文档 + 标签表
uv run python -m tools.embed --check       # 校验向量与 chunks 是否一致
uv run python -m tools.probe_ingested      # 病种覆盖表，离线
uv run python -m tools.build_handoff       # 从实测记录生成阶段二验收用的冻结样本
uv run python -m tools.list_candidates     # 新的下载清单，只碰站点搜索接口
```

`.cache/` 存原始 PDF 与响应，体积大，不入仓库；`corpus/*.json` 记录了来源 URL 与条款数，重跑据此可复现。

## 凭据

模型调用走华为云 MaaS 的 OpenAI 兼容端点，凭据放 `experiment/.env`，不提交。需要 `MAAS_API_KEY`、`MAAS_BASE_URL`。`.env.example` 给出字段名，值留空。
