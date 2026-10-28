# Fund Investment Platform (基金投资平台) 本地启动与运行指南

本文档详细介绍了基金投资平台（Fund Investment Platform）的技术架构、本地启动步骤、各模块访问入口、环境变量配置及常见问题排查。

---

## 目录
- [一、服务架构与组成](#一服务架构与组成)
- [二、运行前置要求](#二运行前置要求)
- [三、方式一：一键极速启动（推荐）](#三方式一一键极速启动推荐)
- [四、方式二：手动分步启动（开发调试）](#四方式二手动分步启动开发调试)
- [五、系统主要访问入口与功能直达](#五系统主要访问入口与功能直达)
- [六、环境变量配置说明](#六环境变量配置说明)
- [七、常见问题排查 (FAQ)](#七常见问题排查-faq)

---

## 一、服务架构与组成

基金投资平台采用现代分离架构设计，各服务职责如下：

```mermaid
flowchart LR
    Browser["🖥️ 浏览器用户界面\n(React 18 + Vite)\nhttp://localhost:5173"]
    API["🔌 后端 API 服务\n(FastAPI / Uvicorn)\nhttp://127.0.0.1:8000"]
    Worker["⚙️ 异步计算 Worker 进程\n(Python Job Runner)"]
    DB[("🗄️ PostgreSQL 数据库\n(开发库: fip_dev / 5432)")]

    Browser -- "HTTP / REST API 请求\n(自动通过 Vite 反向代理 /api)" --> API
    API -- "读写业务数据、任务入队" --> DB
    Worker -- "领跑计算作业 (Lease Lock)" --> DB
```

1. **前端 Web 界面**：基于 React 18、TypeScript、TanStack Query、ECharts 与 Vite 构建，监听端口 `5173`。开发服务器内置反向代理，自动将 `/api` 请求转发到后端。
2. **后端 API 服务**：基于 FastAPI 与 Uvicorn 构建，监听端口 `8000`，提供冻结契约 API、审计追踪和组合/回测路由。实盘/再平衡当前后端使用内存样例，工作台会明确提示不可作为真实持仓或成交数据。
3. **后台 Worker 进程（可选）**：轮询 PostgreSQL 任务队列执行异步优化/回测和基金基本信息、NAV 抓取作业。默认 `./start.sh` 不启动 Worker；任务会留在队列中，需使用 `./start.sh --with-worker` 执行。
4. **PostgreSQL 数据库**：持久化基金、候选池、计算作业与抓取历史。基金抓取及后台任务需要数据库和最新迁移；没有数据库时，API 只能启动，不能提供完整的持久化业务流程。

---

## 二、运行前置要求

在本地计算机运行本平台，需满足以下环境：

| 依赖项 | 推荐版本 | 用途说明 | 检查命令 |
| :--- | :--- | :--- | :--- |
| **Python** | 3.12.x | 运行后端 API、量化算法与领域模型 | `python3 --version` |
| **Node.js** | 18.x / 20.x+ | 运行前端 Web 开发服务器 | `node -v` |
| **npm** | 9.x+ / 10.x+ | 前端包依赖管理 | `npm -v` |
| **PostgreSQL** | 14.x / 16.x | 基金查询、异步任务、抓取历史等持久化业务所需 | `psql --version` |

> [!NOTE]
> 项目原生支持**纯本地模式启动**，无需 Docker 或任何容器守护进程。

---

## 三、方式一：一键极速启动（推荐）

仓库根目录下提供了自动化启动脚本 [`start.sh`](../start.sh)，该脚本会检测依赖和目标端口，启动后端并检查存活探针，再启动前端并检查页面响应。目标端口已有进程监听时会停止启动并提示，不会杀掉或复用未识别的服务。前端首次安装依赖时使用 `npm ci`。

### 1. 执行一键启动
在项目根目录下打开终端运行：
```bash
./start.sh
```

### 2. 命令行选项说明
脚本支持按需传入参数：
```bash
# 同时启动后端 API、前端以及后台 Worker（需先启动 PostgreSQL 并执行迁移）
./start.sh --with-worker

# 仅启动后端 API 服务 (端口 8000)
./start.sh --api-only

# 仅启动前端 Web 开发服务 (端口 5173)
./start.sh --frontend-only

# 查看脚本帮助说明
./start.sh --help
```

### 3. 一键安全停止
在当前运行脚本的终端中按下 **`Ctrl + C`**，脚本会停止由本次启动的 API、前端和 Worker 进程。它不会终止启动前已存在的服务。

---

## 四、方式二：手动分步启动（开发调试）

若需要单独对前端或后端进行独立调试，可按照以下步骤手动启动：

### 步骤 1：准备 Python 虚拟环境与依赖
在项目根目录运行：
```bash
# 1. 创建虚拟环境 (如尚未创建)
python3 -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖锁文件中的依赖包
pip install -r requirements.lock
```

### 步骤 2：启动 PostgreSQL 并执行数据库迁移（可选）
启动完整 API 数据流程和 Worker 前，需要 PostgreSQL、数据库 `fip_dev` 及最新迁移：
```bash
# 执行 Alembic 数据库版本迁移到最新状态
make migrate
```
基金数据抓取依赖当前 Alembic head（含 `0035–0039` 的任务请求/结果、基本信息历史、Worker 起止时间字段，以及范围预览和项级抓取结果）。先确认 `FIP_DATABASE_URL` 指向隔离的开发/验收库，再运行 `make migrate`。`start.sh` 不会自动迁移，也不会清理数据库。
数据库不可用时，后端进程仍可能启动并通过存活探针，但读取/写入业务接口不会因此变为可用。

### 步骤 3：启动后端 FastAPI 服务
在项目根目录运行：
```bash
# 启动 API 服务（开启热重载与 M2 实盘调仓路由）
PYTHONPATH=src FIP_ENABLE_M2_REBALANCE=true .venv/bin/uvicorn fip.api.app:app --host 127.0.0.1 --port 8000 --reload
```
或直接使用 Makefile 快捷指令：
```bash
make api-dev
```
启动成功后，控制台将输出 Uvicorn 监听日志，服务运行于 `http://127.0.0.1:8000`。

### 步骤 4：（可选）启动后台异步计算 Worker
若需要处理异步优化/回测或基金数据抓取作业，另开终端运行：
```bash
make worker-dev
# 或: PYTHONPATH=src .venv/bin/python -m fip.platform.jobs.worker
```

数据抓取中心的单只和多只抓取要求当前 session 有 `can_manage_data_ingestion`；“基金库全量/筛选全量”、以及相应的取消和失败重试还要求 `can_manage_full_universe_ingestion`。该能力默认拒绝，必须由受信任的身份/权限配置显式授予；不要通过浏览器可编辑身份头或前端状态赋权。API 会继续校验 operation 归属和 actor。Worker 使用已配置的真实数据源映射；无映射项会记录为不可抓取/失败明细，不会被当作成功或零值。AKShare NAV 不支持日期范围参数，页面不会提供虚假的日期筛选。

### 步骤 5：启动前端开发服务器
新开一个终端窗口，进入 `frontend` 目录：
```bash
cd frontend

# 安装前端 NPM 依赖（初次运行需执行）
npm install

# 启动 Vite 本地开发服务器
npm run dev
```
启动成功后，浏览器访问 `http://localhost:5173` 即可进入界面。

---

## 五、系统主要访问入口与功能直达

服务启动后，可在浏览器中打开对应 URL 体验全套功能：

### 1. Web 交互看板 (`http://localhost:5173`)
| 功能模块 | 访问路径 | 核心业务能力说明 |
| :--- | :--- | :--- |
| **客户工作台** | [`/home`](http://localhost:5173/home) | 基于当前身份可访问范围展示真实基金库和组合数量，并提供研究入口 |
| **基金研究** | [`/funds`](http://localhost:5173/funds) | 服务端筛选、分页、排序、分类证据；基金抓取操作统一进入数据抓取中心 |
| **数据抓取中心** | [`/data-ingestion`](http://localhost:5173/data-ingestion) | 独立执行基本信息或 NAV 的单只、多只及有权限的基金库快照抓取；需要抓取权限、Worker、数据库迁移和数据源网络 |
| **基金详情** | [`/funds/000001`](http://localhost:5173/funds/000001) | 净值图表、评估/评分归因、分类历史；可跳转到数据抓取中心并预选基金及数据集 |
| **候选池管理与快照** | [`/universes`](http://localhost:5173/universes) | 候选池快照查询、入选/排除结果和 API 实际提供的条件证据 |
| **分类复核** | [`/classification-reviews`](http://localhost:5173/classification-reviews) | 查看待复核分类并按当前用户权限提交复核 |
| **组合决策详情页** | [`/portfolios/P001`](http://localhost:5173/portfolios/P001) | 组合读取、优化提交/结果和决策复核。实盘与再平衡视图会标记后端数据源不可用；当前后端样例数据不代表真实持仓或成交。 |
| **组合策略回测** | [`/backtests`](http://localhost:5173/backtests) | 回测创建、校验、运行状态和 URL 恢复。当前绩效与偏差 API 返回空结果，收益曲线和偏差结论不可用。 |

### 2. 后端开发者与监控入口 (`http://127.0.0.1:8000`)
| 入口说明 | 访问路径 | 功能说明 |
| :--- | :--- | :--- |
| **OpenAPI 交互式文档** | [`/docs`](http://127.0.0.1:8000/docs) | Swagger UI 在线接口调试，支持直接发送参数与查看契约响应 |
| **OpenAPI 契约架构** | [`/openapi.json`](http://127.0.0.1:8000/openapi.json) | 机器可读的 OpenAPI 3.1 规范定义 |
| **存活探针 (Liveness)** | [`/health/live`](http://127.0.0.1:8000/health/live) | 返回 `{"status":"ok"}`，用于判断 Web 进程运行状态 |
| **就绪探针 (Readiness)** | [`/health/ready`](http://127.0.0.1:8000/health/ready) | 检查数据库连接与数据版本迁移就绪状态 |
| **Prometheus 监控指标** | [`/metrics`](http://127.0.0.1:8000/metrics) | 标准 Prometheus 文本格式，输出 API QPS、延迟分布等统计 |

---

## 六、环境变量配置说明

项目支持通过在根目录下创建 `.env` 文件或直接在启动命令前配置环境变量：

| 环境变量名 | 默认值 | 作用说明 |
| :--- | :--- | :--- |
| `FIP_DATABASE_URL` | `postgresql+psycopg://localhost/fip_dev` | 主业务数据库连接字符串 |
| `FIP_ENABLE_M2_REBALANCE` | `false` | 是否开启 Stage ⑨ 实盘持仓与 Stage ⑩ 调仓 API 路由（`start.sh` 已默认开启） |
| `FIP_ENV` | `development` | 运行环境（`development` / `test` / `production`） |
| `FIP_RATE_LIMIT_PER_MINUTE` | `120` | API 令牌桶限流速率（每分钟最大请求次数） |
| `FIP_WORKER_POLL_SECONDS` | `1.0` | 异步计算 Worker 轮询任务队列的间隔秒数 |
| `VITE_API_BASE_URL` | *(空)* | 前端 API 目标基地址（留空时由 Vite 自动代理到本地 8000 端口） |
| `FIP_PYTHON_LOCALE` | `${LANG}`；未设置时 `zh_CN.UTF-8` | 仅由 `start.sh` 用于启动 Python 进程，保证虚拟环境中的 UTF-8 路径可读取；通常无需手动设置 |

---

## 七、常见问题排查 (FAQ)

### Q1: 提示端口 8000 或 5173 已被占用？
启动脚本会停止运行，避免把其他项目误当作本项目服务。先检查监听进程身份，再决定是否停止：
- 查看占用进程：
  ```bash
  lsof -i :8000
  lsof -i :5173
  ```
- 确认是本项目残留进程后，先尝试正常停止对应服务；不要直接对未知 PID 使用强制终止：
  ```bash
  kill <PID>
  ```
- 再次运行 `./start.sh`。

### Q2: 前端请求 API 出现网络错误或 404？
**排查步骤**：
1. 检查后端 API 是否已正常启动：
   ```bash
   curl http://127.0.0.1:8000/health/live
   ```
   若返回 `{"status":"ok"}`，说明后端服务正常。
2. Vite 配置文件 [`frontend/vite.config.ts`](file:///Users/zhukun/学习/fund-investment-platform/frontend/vite.config.ts) 已配置反向代理规则，会无缝把 `/api` 转发到 `http://127.0.0.1:8000`，请确保不要关闭后端服务。

### Q3: 运行 `make api-dev` 提示找不到 `uvicorn` 或 Python 模块？
**解决办法**：请确认是否使用了项目专属的虚拟环境 `.venv`：
```bash
source .venv/bin/activate
which uvicorn
```
或者直接使用仓库内置路径 `.venv/bin/uvicorn` 运行。

---

## 八、常用研发质量验证命令

为保证交付质量，日常开发中可随时执行以下全自动化检查：

```bash
# 运行后端所有单元测试与 API 测试 (400+ 项测试全覆盖)
.venv/bin/pytest tests/unit tests/api -q

# 运行 Python 静态类型严格检查
.venv/bin/mypy

# 运行 Python 代码风格规范检查
.venv/bin/ruff check src

# 运行前端全部 Vitest 测试套件 (112 项测试全覆盖)
cd frontend && npm test -- --run

# 运行前端代码格式与规范检查
cd frontend && npm run check
```
