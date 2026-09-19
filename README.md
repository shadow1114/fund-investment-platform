# Fund Investment Platform

基金投资平台的领域逻辑、数据处理与 M1.7 前端位于本仓库。M1.7 前端是按冻结契约构建的客户端；仓库目前尚无提供该契约的 HTTP Web server。

## 前端

本地启动：

```sh
cd frontend && npm install
npm run api:generate
npm run dev
```

页面需要同源 `/api/v1` 服务才能读取真实数据。路由、接口对应、测试 fixtures 与集成限制见 [前端交接说明](frontend/README.md)。前端完整校验在仓库根目录执行 `make frontend-check`，Python 校验执行 `make check`。
