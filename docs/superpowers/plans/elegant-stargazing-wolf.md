# 基金分类功能实施计划

## Context

依据 `docs/superpowers/fund_classification.txt`（R1–R6），为中国公募基金（含境内发行 QDII）建立可解释、可复核、可历史重放的五维分类功能，完成 **原始资料 → 规则分类 → 版本化落库 → 查询筛选 → Web/CLI 复核 → 新修订** 的闭环。

当前基金列表导入已有原始数据留存，但忽略“基金类型”；`FundClassificationHistory` 只存单码；PIT repository 固定读取 `FIP_INTERNAL_L2`；API/前端只能筛选展示单码。因此不是单纯增加几个枚举，而是补齐分类事实生产与消费链路。

本计划只覆盖分类，不扩展优化、回测或全平台调度。用户已确认：**首版交付 Web 复核 + CLI；strategy 单值采用专属策略优先**。本轮只写计划，不实施业务代码。

## 一、固定交付契约

### 1. 五维标准与证据

- 完整采用需求枚举：`asset_class`、`strategy`、`product_structure` 单值；`geography`、`market_attributes` 多值，去重并稳定排序。
- 分类归属 Fund 产品；A/C/D 等属于 ShareClass。场内交易资格单独保存，不等同于 ETF/LOF 结构，也不等同于申购赎回 eligibility。
- 多值字段中的 `UNKNOWN` 不与确认标签共存。QDII 可以同时具有 CROSS_BORDER，不推导 US；`DOMESTIC` 与 CROSS_BORDER 有矛盾证据时复核。
- 每维独立保存 `CONFIRMED / CANDIDATE / CONFLICT / UNKNOWN`、最终值、候选值及证据。仅名称关键词不能生成已确认值；一个维度冲突不抹掉其他可靠维度。
- 每维证据包含 `source / rule_id / confidence / classified_at`、原始字段和值、原始载荷引用、资料定位及冲突原因。confidence 使用有定义的证据等级，不冒充概率，也不替代 availability_quality。
- `OTHER` 仅用于规则表明确识别的其他产品；新类型/不足证据输出 UNKNOWN 并进入复核。REIT、COMMODITY 必须有正式类型或底层资产依据，不用名称或“指数型”直接猜测。
- `GLOBAL` 对应明确全球授权；`MULTI_REGION` 对应明确多个地域且未声明全球授权；具体市场可多值。相反证据进入复核。

### 2. 已确认的策略优先级

版本化声明：**TARGET_DATE / TARGET_RISK → ENHANCED_INDEX → PASSIVE_INDEX → QUANTITATIVE → ACTIVE → UNKNOWN**。

目标日期和目标风险互相矛盾时复核；指数增强优先于泛化的指数线索，主动增强不被误判被动。量化证据与专属策略可以共存于证据层，但 strategy 仍单值。只有证据描述相容且存在专属/通用关系时使用优先级；权威资料明确矛盾不能靠优先级消除。不因“不是指数”就默认 ACTIVE。

### 3. 下游边界

新方案命名 `FIP_CLASSIFICATION_V1`，规则与枚举均携带版本。旧 `FIP_INTERNAL_L2` 不直接替换为 EQUITY 等资产类别。

建立独立兼容投影：确认的 EQUITY+ACTIVE → ACTIVE_EQUITY，EQUITY+PASSIVE_INDEX → PASSIVE_EQUITY，BOND → BOND，MIXED → HYBRID。增强、量化股票及其他首版未支持组合返回不支持原因，不强塞主动/被动画像。映射只保证旧评价边界兼容，不声称同资产基金必然可比；现有 benchmark/eligibility 校验继续生效。

分类不读取 Score/Universe。未确认产品归组、相关维度冲突或不支持组合不可进入旧评价画像；缺失可追溯。既有 Peer Group/评价快照不重写。

## 二、推荐实施步骤

### 步骤 1：规则契约与纯分类器

新增 `src/fip/services/data_service/classification/`，区分纯规则、证据标准化、写入服务、复核服务；版本化映射配置放 `config/policy/classification/v1.yaml`，复用现有政策加载/版本校验习惯。

纯分类器只接收标准化证据，不做网络/数据库 I/O。实现 R1–R6，并用规则 ID 固定依据：

- 原始正式类型映射资产；纯“指数型”必须核实标的资产。
- 官方投资目标/策略/跟踪标的判策略、地域；业绩比较基准不是跟踪标的，不凭存在指数基准判被动。
- 产品资料或场内产品名录确认结构；ETF 与 ETF_LINKED 严格分离。
- 名称仅生成候选；新类型、冲突、缺失进入可去重的复核事项。
- 保存官方资料、公开聚合源、名称线索的证据等级；优先级不能静默吞掉来源冲突。

**交付门槛**：纯规则矩阵测试通过，再接入采集与持久化。

### 步骤 2：增强模型，建立不可变修订与 PIT

保留 Fund、FundShareClass、ProviderFundIdentity、原始载荷及现有分类历史表；首版没有证据支持删除任何现存表，不修改旧 migration。

推荐数据结构：

1. 新增 `FundClassificationRevision`：产品/方案、递增 version、规则版本、内容哈希、classified_at、available_at、来源时间与质量、修订原因、操作者；保留旧版本。
2. 增强 `FundClassificationHistory`：新增 revision_id、五维完整结果、每维状态/证据/候选 JSONB、独立场内资格信息；保留 legacy scheme/code/时间列。每个修订保存完整有效区间集合。
3. 新增 `FundClassificationReviewCase`：产品、基线 revision、问题类型、待处理/已解决状态、证据引用；审核行为复用治理 AuditLog，不再造平行审计表。

约束：修订 `(fund_id, scheme, version)` 唯一；同修订区间不重叠且最多一条开放区间；字段枚举、标签唯一性、UNKNOWN 互斥、证据结构及区间合法性由应用与数据库适当分工校验。新增 Alembic revision，ORM 同步声明。

**PIT 算法**：先筛选 `available_at <= decision_at`（日期入口复用 `visible_until_for()`），按 version 最大选修订；再从该修订选择覆盖业务日期的 `[valid_from, valid_to)` 区间。不能先筛区间再跨版本挑行，不能用 available_at 或 id 代替修订版本排序。

转型、回溯纠正、人工复核均追加新 revision：复制完整区间集合后在新版本分割/纠正；旧区间不原地关闭或覆盖。新版区间缺口返回缺失，不偷偷回退旧结果。按产品/方案事务锁分配版本，修订头、区间、复核状态和审计同事务提交。

用证据/结果/规则版本哈希保证重复导入不产生重复有效修订；新证据需要留存，新抓取时间不作为唯一内容变化。人工确认结果不会被后续自动刷新无条件覆盖，可靠新证据形成复核或明确转型修订。

**旧数据迁移**：legacy 行与原有时点原样保留，旧读路径保留至切换验收；新列兼容旧行。调整 `uq_fch_open_interval` 为 legacy 部分约束＋按 revision 隔离的新约束。旧分类不能反推成可靠五维证据；已丢失的区间修订不伪造恢复。对新五维事实只使用真实可用时间，不用成立日回填 available_at。

### 步骤 3：采集、身份保护与 CLI

复用现有 `ensure_dataset()`、原始载荷留存/列校验、`IngestService.ingest_fund_list()`、ProviderFundIdentity 和时间质量机制：

- 基金列表导入消费“基金类型”，产生资产证据并分类落库；未知类型产生报告而非丢弃。
- 增加 `fund_overview_em` 数据集及适配，抽取正式类型、投资范围、跟踪标的等可得资料。雪球资料和 ETF/场内名录作为辅助证据源按需接入；只有名称或接口无字段时保持 UNKNOWN，不编造确认依据。
- 各新数据集配置有界超时、限速、有限退避重试和字段契约测试；仅瞬时网络/限流失败重试，解析契约变化报错并保留 raw。AKShare 无 timeout 参数的调用使用可终止的隔离调用，不能使用超时后线程仍永久占用的伪超时。
- 不机械套用净值披露时滞。资料发布时间与检索、分类完成、复核完成时间分开保存；无历史发布时间的当前资料不宣称历史精确可见。
- 提供 `classify-funds`（过滤/批量/预览/幂等）、`refresh-classification`、`list-classification-reviews`、`review-classification`。Web 和 CLI 调用同一写入/审核服务；CLI 显式记录操作人并使用项目操作授权边界，不冒充 HTTP 会话。

收紧 `grouping.py`：名称后缀只能产生份额候选；需官方份额名称、产品关联和管理人等证据才能确认合并。已有可疑分组只报告并复核，不批量拆解身份或搬迁历史外键。ETF/联接产品、同名不同管理人不得合并。

### 步骤 4：统一查询与评价兼容

扩展 `SqlClassificationPitRepository` 和 `ClassificationPoint`，新增五维快照读取接口，保留旧调用适配。列表、详情、复核读取共享同一 PIT 选择逻辑，避免各自实现“取最新”。

新增分类到旧 L2 的纯投影，记录 mapping_version、revision_id。让既有 PeerGroup 输入适配消费确认分类并输出明确排除原因，复用 `build_peer_groups()` / `excluded_candidates()`；不增加对评分或候选池的依赖。

详情返回真实 classification revision/version，不再把 valid_from 日期当版本。旧 `classification_version` 日期字段先按冻结契约保留为兼容字段，新增结构化 `classification.version/revision_id/valid_from`；同时更新前端改用新字段，文档声明弃用，避免静默改变旧字段语义。

### 步骤 5：API 与 Web 分类复核

扩展现有 `/api/v1/funds` 列表/详情：新增五维分类对象、每维状态、来源概要、规则版本与真实修订标识。新增五维 query 参数；维度间 AND、同维度内 ANY，地域/市场属性使用集合交集；保留旧 fund_type 过滤。未确认维度的候选值不命中确认值筛选，可通过 status 查询候选/冲突。

推荐新增分类字典、历史、待复核列表/详情和复核提交接口：`GET /fund-classifications/catalog`、`GET /funds/{fund_id}/classification-history`、`GET /classification-reviews`、`GET /classification-reviews/{case_id}`、`POST /classification-reviews/{case_id}/review`（均在 `/api/v1` 下）。历史接口携带 decision_at 过滤，不通过“历史页面”绕开可见时点。

复核提交要求 expected_revision、维度决定、理由、证据；支持确认候选、覆盖及驳回候选（驳回后保留 UNKNOWN，不当作已确认）。旧基线或重复失效提交返回409；无权限403。扩展 Principal 的分类复核 capability，并为 AuditWriter 增加分类资源入口，不复用硬编码 decision 的资源类型。

前端交付：

- FundFilters 使用字典驱动的五维单/多选，保留搜索与已有筛选语义；URL、React Query key 包含全部过滤参数。
- FundTable/FundDetail 展示分类、候选/冲突/UNKNOWN、来源与规则版本，详情可查看证据和可见历史；不把候选伪装为最终分类。
- 新 `ClassificationReviewPage` 提供分页队列、维度证据比较、确认/覆盖/驳回表单；按服务端 capability 显示操作，409 后重新加载，不自动覆盖。
- 同步 `schemas.py`、路由、OpenAPI 投影 `frontend/openapi/m17.yaml`，运行 Orval 生成客户端；禁止手改 generated 文件。

### 步骤 6：兼容验收与发布

先执行迁移和定向回归，再导入离线代表性样本进行端到端验收，最后对获授权的真实公开数据做小批量试跑。真实批量刷新先 dry-run，输出新类型、缺失率、冲突率和可疑归组清单，确认后分批落库。迁移/发布前备份；生产数据回滚不能靠破坏性 downgrade 丢弃审核和历史。

文档改动实施前完整读取 `docs/01-product/01-product-overview.md`，按需同步数据域与 `docs/10-api/06-m17-frontend-contracts.md`；遵循升版本、补变更记录、更新依赖声明和下游级联。需求 txt 保留原样。

## 三、关键文件与复用点

| 范围 | 修改/新增位置与复用内容 |
|---|---|
| 规则 | 新 `services/data_service/classification/`、`config/policy/classification/v1.yaml` |
| 模型迁移 | `src/fip/services/data_service/models/fund.py`、新 Alembic revision（当前 head 0033，实施时再确认）、`db/migrations/env.py`（仅新增独立 ORM 模块时注册） |
| PIT | `src/fip/services/data_service/repositories/classification.py`、`src/fip/platform/decision_data/pit.py`；复用 `visible_until_for()`、IntervalMixin 时间来源与区间约束，不全局改变其他历史表 |
| 采集 | `services/data_service/adapters/akshare/{datasets,client}.py`、`services/data_service/ingest.py`；复用数据集注册、raw 留存、ProviderFundIdentity |
| 身份 | `services/data_service/grouping.py`，保留 Fund/ShareClass 分离 |
| CLI | `src/fip/platform/cli.py` |
| 评价兼容 | `services/fund_service/peer_group/{builder,models}.py` 与候选输入适配，`config/policy/evaluation/v1.yaml` 不原地改既有版本 |
| API | `src/fip/api/{repositories,fund_queries,schemas,context,auth,audit}.py`、`routers/reads.py`、新分类复核 router、`app.py` 注册 |
| 前端 | `frontend/src/features/funds/{FundFilters,FundTable}.tsx`、`pages/FundDetailPage.tsx`、新复核页面及现有路由入口、OpenAPI/Orval |
| 测试 | 分类规则单测、PostgreSQL分类/PIT/迁移测试、`tests/api/test_fund_routes.py` 及新增复核契约测试、Vitest/MSW fixtures 与 Playwright |

## 四、验证与验收标准

### 必须覆盖的场景

1. 股票/债券/混合/货币/FOF 正式类型；纯指数不默认 EQUITY；REIT/商品名称只能候选；新类型保留原值。
2. 增强与普通被动区别；量化＋指数专属优先；明确矛盾证据待复核；缺证不默认 ACTIVE。
3. QDII 不推出 US；多地域、GLOBAL/MULTI_REGION、标签 UNKNOWN 互斥。
4. ETF/联接不合并；A/C 不作资产类别；同名不同产品不误归组；已有历史外键不改写。
5. 多源证据冲突、人工确认不被刷新覆盖、幂等导入、并发版本分配、过期复核409、权限403与审计同事务。
6. 迟到资料、同日多次修订、未来生效、转型区间关闭、回溯纠正：**新增修订后旧 decision_at 的查询结果不变**；取最大可见 version；缺口不回退。
7. 迁移保留旧行及旧 API 行为；五维组合筛选与分页正确；未确认候选不命中确认筛选；真实版本与来源在详情一致。
8. 旧评价画像边界保持，增强/量化不误入被动组；历史快照不重写；ORM/迁移 metadata 和 OpenAPI parity 通过。
9. Web E2E：查询基金 → 五维筛选 → 查看证据 → 待复核 → 人工确认 → 当前结果更新 → 历史时点不变。浏览器拦截 smoke 不替代真实 PostgreSQL/API 集成验收。

### 验证命令

先分类相关定向测试，再运行：

```sh
make lint
make typecheck
make test-unit
make test-fitness
make api-check
make test-integration
make test-api-integration
make frontend-api
make frontend-check
```

联网 AKShare 契约使用 `make test-contract` 单独运行，不要求外部源可用性决定纯规则测试结果。真实 Web 联调复用 `make api-dev` / `make frontend-dev`，不依赖尚未接通的优化/回测 worker。

**安全前置条件**：`tests/conftest.py` 的 fixture 会删除并重建 schema，所有集成测试须确认 `settings.test_database_url` 指向可丢弃的专用测试库，禁止开发/生产库。Playwright 会启动后端与 Vite；generated 代码由 `make frontend-api` 产生，并通过 `tests/api/test_openapi_parity.py`、响应契约与前端类型检查验证。

### 完成定义

首版必须能从原始基金类型/详情证据生成并持久化五维分类，未知与冲突可通过 Web/CLI 复核；基金列表/详情/筛选消费同一 PIT 修订；审核、来源、规则与历史可追溯；旧分类消费者兼容且无误分组。仅定义枚举、只展示 mock 或仅新增表均不算完成。
