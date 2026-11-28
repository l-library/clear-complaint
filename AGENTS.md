# ClearComplaint agent guidelines

Engineering conventions for everyone working on this repo: team members and AI agents alike. Product background and delivery plan live in [docs/PLAN.md](docs/PLAN.md); competition rules and platform limits live in [docs/赛题调研.md](docs/赛题调研.md). This file mirrors [CONVENTION.md](CONVENTION.md), the Chinese original. Change both in the same commit.

## 1. Project layout

ClearComplaint is a split frontend and backend application. `frontend/` is one uni-app codebase compiled to H5 and to a WeChat mini program. `backend/` is a FastAPI monolith with dependencies managed by uv. Postgres runs in Docker. The repo is a monorepo.

```
.
├── backend/                        FastAPI monolith, uv manages deps and the venv
│   ├── app/
│   │   ├── main.py                 App factory, the only place the /api prefix appears
│   │   ├── core/config.py          Settings (pydantic-settings, reads .env)
│   │   ├── common/
│   │   │   ├── api.py              ApiResponse, ok()/error()
│   │   │   ├── codes.py            ErrorCode enum
│   │   │   ├── errors.py           BizException, global exception handlers
│   │   │   └── web.py              /ping, /health
│   │   ├── db/
│   │   │   ├── base.py             DeclarativeBase
│   │   │   └── session.py          Engine, session factory, get_session dependency
│   │   ├── api/__init__.py         Router aggregation, prefix mounted once in main.py
│   │   └── <domain>/               One package per domain: router/service/schema/models
│   ├── alembic/                    Migrations, versions/ starting at V1
│   ├── alembic.ini                 No connection string here, env.py reads it from settings
│   ├── tests/                      Tests mirroring the modules they cover
│   ├── pyproject.toml              Dependencies plus ruff, mypy, pytest config
│   └── .env.example                Copy to .env
├── frontend/                       uni-app project for H5 and WeChat mini program
│   ├── src/pages/                  Pages, registered in src/pages.json
│   ├── src/api/                    Request functions grouped by domain
│   ├── src/request/                Request wrapper shared by H5 and the mini program
│   ├── src/pages.json              Five page routes plus globalStyle; no tabBar, no subpackages
│   ├── src/manifest.json           Per-platform config including the WeChat appid
│   ├── scripts/                    Node check scripts: check:interactions (CI), check:live (manual)
│   ├── vite.config.ts              H5 dev proxy for /api (targets port 8000)
│   └── pnpm-workspace.yaml         All pnpm 12 settings: build allowlist and nodeLinker
├── experiment/                     Stage one research artifact: own uv project, never imports backend
│   ├── corpus/                     Guideline fragments, frozen vectors, term list, department list, red flag list
│   ├── cases/                      Cases, five variant families, gold labels, sign-off records
│   ├── harness/                    Normalization, red flags, retrieval, gates, model client, and the four arms' prompts and switches (arms.py)
│   ├── runs/                       Raw responses and parameters, append only
│   ├── analysis/                   Metrics, bootstrap, figures/
│   └── handoff/                    Constraint spec and frozen sample for stage two acceptance
├── docs/                           PLAN.md, stage1.md, FRONTEND_WORKSPACE.md, api.md, api-agentarts.md, daily-companion.md, 赛题调研.md, preview/, requests/
├── docker-compose.yml              Local Postgres 16
├── start-local.ps1                 Windows helper: Docker, Postgres, backend, H5 (section 2)
├── .github/                        CI and issue templates
├── .editorconfig                   Editor formatting rules (enforced by tooling)
├── .gitattributes                  Line ending rules (enforced by git)
├── CONVENTION.md                   Chinese original
├── AGENTS.md                       This file, English mirror
├── CLAUDE.md                       Points at AGENTS.md
└── README.md                       Product background and stack
```

- The backend groups code by feature, not by technical layer. No `routers/`, `services/`, `models/` folders. One package per domain, and cross-package imports only reach `common`, `db`, and the other package's service.
- `experiment/` holds stage one: a standalone uv project that never imports `backend/`, and that the backend never depends on. When stage two needs its normalization, red flag, or citation gate logic, copy it into `backend/app/` and keep both running independently instead of merging them into one package.
- Inside a domain package: `router.py` for routes, `service.py` for business logic, `schema.py` for request and response models, `models.py` for ORM models. Do not create empty files for parts that do not exist yet.
- Frontend pages live at `src/pages/<module>/<page>.vue`. Components start with `Q`.

## 2. Development environment

- Python 3.14, managed by uv. `backend/.python-version` pins the version and `uv sync` prepares the interpreter and virtualenv, so do not run `python -m venv` by hand. Do not install dependencies with system pip.
- uv 0.13 or newer. Every dependency change goes through `uv add`, `uv add --dev`, or `uv sync`. Do not hand-edit versions in `pyproject.toml` to match the lockfile.
- Node 26 with pnpm 12. pnpm 12 reads settings only from `frontend/pnpm-workspace.yaml` and no longer reads `.npmrc`. Two entries there cannot be removed: `allowBuilds` lets dependency postinstall scripts run (without it `pnpm install` fails with `ERR_PNPM_IGNORED_BUILDS`), and `nodeLinker: hoisted` keeps a flat node_modules (under the isolated layout, uni-app's rollup cannot resolve pinia's transitive dependencies and `pnpm build:h5` fails).
- Docker and Docker Compose. Postgres runs only in a container. The Docker daemon must be running (`docker info` has to succeed), otherwise compose commands fail outright.
- Application processes stay outside containers: uvicorn for the backend, the Vite dev server for the frontend. Reasons are in section 8.
- `start-local.ps1` is a Windows-only convenience wrapper, listed in the table below. It needs `backend/.env`, keeps existing database data, serves H5 on 5175 rather than the 5173 that `pnpm dev:h5` uses, writes logs to the git-ignored `.tools/runtime/`, and never stops a process it did not start.

| Command | Effect |
| --- | --- |
| `docker compose up -d` | Start Postgres (5432), data in the named volume `clear-complaint-db-data` |
| `docker compose logs -f db` | Follow database logs |
| `docker compose down` / `down -v` | Stop; the second form also deletes data |
| `./start-local.ps1` | Windows only: start Docker, Postgres, the backend and the H5 dev server on 5175 |
| `cd backend && uv sync` | Install dependencies and prepare the venv |
| `cd backend && uv run uvicorn app.main:app --reload` | Start the backend on 8000, routes under `/api` |
| `cd backend && uv run pytest` | Backend tests (needs the dockerized Postgres) |
| `cd backend && uv run alembic upgrade head` | Migrate to the latest revision |
| `cd backend && uv run alembic revision -m "message"` | Create a migration |
| `cd frontend && pnpm install` | Install frontend dependencies |
| `cd frontend && pnpm dev:h5` | H5 dev server on 5173, `/api` proxied to 8000 |
| `cd frontend && pnpm dev:mp-weixin` | Mini program output, open `dist/dev/mp-weixin` in WeChat devtools |
| `cd frontend && pnpm type-check` | vue-tsc type check |
| `cd frontend && pnpm check:interactions` | Offline check of auth, refresh, SSE parsing and the chat flow; runs in CI |
| `cd frontend && pnpm check:live` | Manual end-to-end check against a running local stack, with a temporary synthetic account |
| `cd frontend && pnpm build:h5` | Frontend sanity check; run it with type-check before committing |
| `cd frontend && pnpm build:mp-weixin` | Mini program production build in `dist/build/mp-weixin` |

Before committing, run `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` for the backend and `pnpm type-check && pnpm check:interactions && pnpm build:h5` for the frontend. Also run `git diff --check` to catch whitespace and line ending problems.

## 3. Git workflow

### 3.1 Branches (main and feature branches only)

- `main`: the stable branch, runnable at any time. Only pull requests merge into it; direct pushes are rejected by the GitHub ruleset (`push declined due to repository rule violations`).
- `feat/<name>`: feature branch cut from main and **deleted immediately** after its PR merges. Use `fix/<name>` for pure bug fixes.
- Names are kebab-case English phrases such as `feat/triage-card` or `fix/mp-proxy-loop`.
- One branch carries one thing (a feature or a fix), merged when done. Do not let branches pile up.

### 3.2 Commit messages (Conventional Commits)

- Format: `<type>(<scope>): <subject>`. Type and subject are in English, the subject is imperative, at most 72 characters, no trailing period. Scope is optional.
- Types: `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore`.
- The optional body explains **why**, wrapped at 72 characters. The footer can carry `Closes #123` or `BREAKING CHANGE: ...`.
- One commit does one thing. Do not mix unrelated formatting changes into a feature commit (see section 4).

Example:

```
feat(triage): reject duplicate evidence indexes

The gate accepted the same index twice and produced a duplicated citation.
Closes #34.
```

### 3.3 Pull requests

- The title follows the Conventional Commit format. The description says at least: **why**, **what changed**, and **how it was verified** (commands run, manual checks done). UI changes include a screenshot or recording.
- Before merging:
  - The GitHub ruleset requires a PR, and both the `backend` and `frontend` checks must pass. The required approval count is currently 0, so you may merge your own PR; to require review, change the ruleset rather than this document.
  - Backend changes have run `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`. Frontend changes have run `pnpm type-check && pnpm check:interactions && pnpm build:h5`.
  - Schema changes replay the migrations from an empty database (`docker compose down -v && docker compose up -d`, then `uv run alembic upgrade head`).
  - CI (`.github/workflows/ci.yml`) is fully green: the `backend` job runs lint, format check, mypy, and pytest; the `frontend` job runs `pnpm install --frozen-lockfile`, `type-check`, `check:interactions`, `build:h5`, and `build:mp-weixin`.
- Merge with a **merge commit** so history is preserved. The ruleset allows only that; squash and rebase are rejected. During review, appending commits or force-pushing to the branch is fine; history does not need to be tidied before merging.
- Delete the feature branch after merging, and link the issue with `Closes #N` in the PR description or commit footer.
- Keep PRs small and focused. Split large changes into several PRs.

## 4. File formatting

- Every text file is **UTF-8 without BOM, LF endings**. The only exception is `*.bat` and `*.cmd`, which use CRLF.
- Indentation is spaces, with widths set in [.editorconfig](.editorconfig): **4 spaces** for Python, **2 spaces** for frontend files (`*.ts` `*.vue` `*.js` `*.json`) plus YAML and Markdown.
- Files end with one blank line, and trailing whitespace is removed. Markdown is exempt because two trailing spaces mean a hard line break.
- [.editorconfig](.editorconfig) and [.gitattributes](.gitattributes) are machine-enforced. Enable EditorConfig support in your IDE, and use `git diff --check` before committing.
- Python formatting and import order come from `ruff format` and `ruff check --fix`. Do not align code by hand.
- Do not reformat whole files inside an unrelated commit.

## 5. General coding practice

### Before changing code

- Do not guess. Read the files and the callers first, understand the affected flow, and do not assume behavior.
- Do only what was asked. No drive-by refactors, no unrelated formatting, no unrelated fixes. Record out-of-scope problems and handle them separately.

### Implementation

- Decision ladder, stop at the first option that solves the problem: does this need to exist, reuse an existing implementation in the repo, use the standard library, use a native platform feature, use an already-installed dependency, write one clear line, otherwise write the smallest working implementation.
- Prefer deletion over addition. Fewest files, smallest diff.
- Write boring code, not clever code. Avoid extra abstraction, single-implementation interfaces, speculative configuration, and scaffolding for future needs.
- Fix the root cause, not the symptom. Before changing shared behavior, look at every caller and fix the common path when you can.
- Comments explain **why**, not **what**. If a name says it, skip the comment.

### Non-negotiable

- Boundary input validation, error handling that prevents data loss, security controls, accessibility, and correctness on relevant edge cases. No simplification may trade these away.
- **This project's own non-negotiables**: the triage level always has a fallback, red flag rules never consult the model, every cited conclusion must be checkable against its source text, and model output never becomes **medical-conclusion** copy directly: conclusions pass the gates and stay auditable, while the narrative layer is model-generated communication text bound by post-generation assertion checks (no new medical claims, in-vocabulary conditions, controlled departments, no dosage advice — see docs/narrative-layer.md). Changes to those areas get their own PR with an explanation.
- Secrets, tokens, and personal configuration never enter the repo. Health data never enters test fixtures; tests use synthetic data.
- Types must pass `mypy` in strict mode. Do not escape with `Any` or `# type: ignore`; if an ignore is genuinely needed, state why.
- Non-trivial new logic ships with one minimal runnable check. Backend tests are pytest tests whose layout and names mirror the code under test, asserting concrete inputs and outputs rather than abstract stubs. The frontend has no test framework, so changes are verified with `pnpm type-check`, `pnpm check:interactions`, `pnpm build:h5` and `pnpm build:mp-weixin`, the four commands CI runs; adding a framework requires registering it in section 8 first.

## 6. Backend and database specifics

- Port 8000. The `/api` prefix appears exactly once, in `app/main.py`'s `include_router`. **Domain routers never write `/api`.**
- Every business endpoint returns the same envelope:

```json
{ "code": 0, "message": "ok", "data": {} }
```

  `code == 0` means success; any other value is a business error defined in `ErrorCode` at `app/common/codes.py`. The frontend checks `code` only and does not parse `message`. HTTP status codes still carry meaning: 400 invalid parameters, 401 unauthenticated, 403 forbidden, 404 not found, 500 server error.
- Pagination uses `data = { records, total, page, size }`. No list endpoint exists yet; use this shape when one lands.
- Time is `Asia/Shanghai`, and responses carry `yyyy-MM-dd HH:mm:ss` strings.
- The health check is `/api/health` and it **does not touch the database**. The test suite does need Postgres: pytest rebuilds `clear_complaint_test` and runs the Alembic migrations every session, so run `docker compose up -d` locally, and the CI backend job carries a `services: postgres` entry.
- Raise `BizException(ErrorCode.XXX, "optional message")` for business errors; the global handlers turn it into the envelope. Unmatched paths and unsupported methods are already mapped to the right error code, so they never fall into the catch-all 500.
- Database access uses SQLAlchemy 2.x async with asyncpg. Inject sessions with `Depends(get_session)`; never call `SessionLocal()` inside a route. Models inherit from `Base` in `app/db/base.py`.
- **Never create tables from code**: no `Base.metadata.create_all`, no hand-written `CREATE TABLE`. Only Alembic migrations create schema.
- Migrations: `uv run alembic revision -m "message"` generates a script with an auto-incrementing revision id. Never edit a committed migration; add a new revision instead. Import new models into `alembic/env.py` so autogenerate can see them.
- Table and column names are `snake_case`, and table names are singular (`episode`, `citation`). Primary keys are `BIGINT GENERATED BY DEFAULT AS IDENTITY`. Timestamps are `created_at` and `updated_at`, typed `TIMESTAMPTZ NOT NULL DEFAULT now()`.
- Database name is `clear_complaint`; the local credentials `clear_complaint` / `clear_complaint` appear in `docker-compose.yml` and `.env.example` and are for local use only. Production reads `DATABASE_URL` from the environment. Never commit real credentials.
- Dependencies are declared in `pyproject.toml` under `[project].dependencies` for runtime and `[dependency-groups].dev` for development. Add them with `uv add`; do not hand-write versions.
- AgentArts platform notes: its invocation endpoint is an SSE stream, requests must carry `x-hw-agentarts-session-id`, and the platform's free model quota cannot be used for API calls, otherwise it returns `Model call failed`. That client is wired up, and section 8 records the runtime versions in use.

## 7. Frontend specifics

- The base is the official uni-app `vite-ts` template. The versions of `@dcloudio/*`, `vite`, `typescript`, and `vue-tsc` are the template's locked combination. **Do not upgrade any one of them alone**; switch the whole template version instead.
- Only H5 and the WeChat mini program, with their `dev:` and `build:` scripts, are kept. Adding other targets (App, Alipay mini program) starts with an issue; do not install them back on a whim.
- The mini program must not touch `window`, `document`, or DOM APIs. Express platform differences with conditional compilation (`// #ifdef H5`, `// #ifdef MP-WEIXIN`). Prefer `rpx` for layout and `@media` breakpoints for wide screens.
- Requests go through `src/request/` only. Pages never call `uni.request` or `axios` directly. H5 uses the relative path `/api`, proxied by Vite to 8000, so backend hostnames never appear in code. The mini program has no proxy, so `request` falls back to `VITE_API_BASE`, defaulting to `http://localhost:8000/api` locally; a real device needs an ICP-filed HTTPS domain.
- State uses Pinia, already registered in `src/main.ts`. Stores live in `src/stores/`; keep cross-page state there.
- Styles start as plain CSS. Variables in `uni.scss` need the `sass` dependency, so add it only when nesting or theming actually requires it. No UI component library and no atomic CSS for now (section 8).
- Conditional compilation comments work in `.ts` too, but `vue-tsc` sees the unprocessed source: do not declare the same `const` in both the `#ifdef` and `#ifndef` branches. Use `let` plus conditional assignment, otherwise type checking reports a duplicate declaration.
- The WeChat mini program main package is capped at 2MB. Serve images from a CDN or external host, and split pages into `subPackages` as the app grows. The mini program appid has not been applied for; `manifest.json` leaves it empty.

## 8. Deferred decisions

The table lists what we deliberately put off. Doing any of it means changing this table first, then the code.

| Item | Status | Notes |
| --- | --- | --- |
| Account tables (V1, V2), episode tables (V3: `episode`/`episode_answer`/`idempotency_key`/`reminder`), archive tables (V4: `vital`/`medication`/`medication_plan`), followup (V5: `followup_record` plus `reminder.dedupe_key`), export (V6: `export_token`), episode revision columns (V7: `episode.revision`/`result_history`/`understanding`/`raw_answers`) | Created | Tables land per domain, field design per docs/api.md |
| AgentArts client | Wired | `app/agent/client.py` transport plus the `app/episode/platform.py` and `app/reminder/platform.py` seams; episode generation, clarification, fallback (M4) and the followup supplement (M6c) run against the real platform. Triage is on the Issue31Fix runtime (`2026-11-26.mainflow-io.6.issue31.1`, runtime `agent-arts-c0c1711a193e454cb169a2091be6d0e9`) with `request.v2`/`workflow.v2` (raw text in, understanding out): single-question clarify with backend-assigned ids, the 10/5 ask ledger, result revisions with capped lookback, out-of-coverage valve, crisis short-circuit before any platform call, and #25 history context in every request; the v1 pre-shaping and the io.5-era fixups are deleted. Profile and followup keep `.2` runtime versions, while the request `schema_version` literals in code are `clear-complaint.profile-intake.request.v1` and `clear-complaint.followup-supplement.request.v1`. Its predecessor, the RouteSafe runtime `2026-11-26.mainflow-io.6`, passed HTTP auth on 2026-11-26 (see #23) and ran the 22-scenario regression pack the same day (17/23 pass, the 4 failures platform-side, tracked in #31); Issue31Fix re-verified 14/14 with zero 4004. #31 stays open pending two platform clarifications. The QA and constraints endpoints are not done |
| Daily health companion (Daily-Health-Companion workflow) | Planned | Contract in private handoff doc 16.8; published URL verified 2026-11-24 (four acceptance cases plus two negative tests pass). Plan in docs/daily-companion.md; D0 is registration only, D1-D3 are backend (settings, client mapping, `app/daily` package, `daily_report` migration), D4 is the frontend page, D5 defers real device adapter, scheduler and push. The key appeared in plaintext in the handoff screenshots; rotate before production use |
| Normalization, red flag short-circuit, citation gate, vocab and department tables | Written (M5) | `app/agent/normalize.py, redflag.py, citation.py, vocab.py, departments.py` plus `data/` (three frozen tables, version 1), copied from experiment and maintained independently; test assertions come from handoff/constraints.md, and `test_normalize_parity.py` pins both replacement tables to the experiment source by parsing it (neither project imports the other). Known edges: the 6-char negation window swallows a second true hit immediately after a negation; `COLLOQUIAL_MAP` doubles as the followup/archive surface list, so the disease-name mapping (慢阻肺 → 慢性阻塞性肺疾病（COPD）) can appear in followup watch-for copy |
| Authentication | Done (account domain) | HS256 access token 2h, refresh token 30d with rotation (replay is 1005); register/login/refresh/logout live, other domains adopt `get_current_user` as needed |
| Mini program appid | Not applied | Required before testing on a real device |
| Test database | Wired | `tests/conftest.py` rebuilds `clear_complaint_test` every session (env `TEST_DATABASE_URL`, default `localhost:5432`) and runs `alembic upgrade head`; the CI backend job carries `services: postgres` |
| Redis | Not added | Do not add the dependency yet |
| Record import (病历上传 / OCR) | Not built | No backend interface; the UI marker was removed. Land it after the object-storage row above is decided; no mock import |
| Consult-side extras (constraint detail, correction scoring, before/after comparison) | Not built | 连续追问 (post-result supplement) landed with request.v2 in #29: the composer feeds the same episode and results are revised with capped lookback. The remaining three items stay on the roadmap, one PR each, no mock data |
| Object storage (image upload) | Not chosen | Wait until there is a real upload need |
| API docs and frontend type generation | Not wired | FastAPI ships OpenAPI; `openapi-typescript` is the candidate |
| UI component library, UnoCSS, `sass` | Not added | Plain CSS for now |
| Frontend test framework | Not added | Two Node scripts instead: `pnpm check:interactions` (offline, runs in CI) and `pnpm check:live` (manual, against a local stack). `pnpm type-check`, both builds, and manual checks still decide |
| Containerized deployment of the apps | Deferred | Apps stay outside containers during development; add `backend/Dockerfile` and `docker-compose.prod.yml` (nginx serving `frontend/dist`) when there is a server |
