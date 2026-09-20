# Fund Investment Platform

基金投资平台的领域逻辑、数据处理、M1.7 前端和冻结契约 API server 位于本仓库。API 层使用 FastAPI，路径由 `frontend/openapi/m17.yaml` 冻结投影驱动。

## API/Web server

安装依赖后，在仓库根目录启动：

```sh
make api-dev
```

服务默认监听 `http://127.0.0.1:8000`，OpenAPI 文档位于 `/docs`，契约 JSON 位于 `/openapi.json`。API 测试和路径校验使用 `make api-check`。开发环境会从 `X-User-ID`/`X-Roles` 读取临时身份；生产认证中间件接入前不能将其视为生产鉴权。数据库连接沿用 `FIP_DATABASE_URL`。

Plan-6 增加本地作业进程：`make worker-dev` 轮询 PostgreSQL 中的计算作业；API 就绪检查使用 `make api-health-check`。两者均为本地命令，不需要容器。

Plan-6 完整验收使用 `make plan6-check`，会依次运行 Python/API/PostgreSQL/Worker 检查和前端检查。

Plan-7 响应契约验收使用 `make plan7-check`，会检查 20 个领域操作的嵌套模型、PostgreSQL 可用性、OpenAPI 生成类型和前端全套校验。该命令只使用本地命令与 PostgreSQL，不启动 Docker。

## 前端

本地启动：

```sh
cd frontend && npm install
npm run api:generate
npm run dev
```

页面需要同源 `/api/v1` 服务才能读取真实数据。路由、接口对应、测试 fixtures 与集成限制见 [前端交接说明](frontend/README.md)。前端完整校验在仓库根目录执行 `make frontend-check`，Python 校验执行 `make check`。
