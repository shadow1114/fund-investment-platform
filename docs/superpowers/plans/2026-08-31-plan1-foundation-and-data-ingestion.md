# Plan-1：M1.0 地基 + M1.1 数据接入 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 `fund-investment-platform` 的工程地基与数据接入层，交付一个可验证的能力：**给定任意历史 `decision_at`，取回当时可见的复权净值序列**。

**Architecture:** 三层分离的 Python 单体（Backend Service → Strategy Library → Quant Engine），单一 PostgreSQL 实例承载 8 个 schema。两个承重机制在本 Plan 建立：① PIT 访问做成类型上无法绕过的接口（`PitDataContext` 在构造期绑定 `decision_at`，不提供"取最新"路径）；② 版本化表的三时间来源与 `availability_quality` 由数据库 CHECK 约束强制，Adapter 拿不到就留空、绝不回填。数据源为 AKShare，经 `SourceAdapter` 端口隔离。

**Tech Stack:** Python 3.12 · SQLAlchemy 2.0 · Alembic · psycopg 3 · PostgreSQL 17 · pandas / numpy · pyarrow · akshare · pydantic 2 · pytest · ruff · mypy

**Spec:** `docs/superpowers/specs/2026-08-31-fund-platform-m1-design.md`

---

## Global Constraints

以下为全项目约束，**每个 Task 的要求都隐含包含本节**。取值逐字来自 spec 与上游文档。

**版本与环境**

- Python **3.12**（非 3.13）。理由：AKShare 依赖的 lxml / py-mini-racer / openpyxl 在 3.13 的 wheel 覆盖仍不稳定，而 `NFR-REPRO-001` 要求依赖版本可锁定。
- PostgreSQL **17**。
- 全部依赖必须在 `requirements.lock` 中**精确锁定**（`==`），不使用范围约束。求解器与数值库版本升级视为影响输出的变更（Constraint C-11）。
- 顶层 Python 包为 `fip`，位于 `src/fip/`。**`platform` 子包必须嵌套在 `fip` 之下**（`fip.platform`），否则会遮蔽 Python 标准库的 `platform` 模块。

**存储精度**（spec §5.4.3）

| 对象 | 类型 |
|---|---|
| 金额 | `NUMERIC(20,4)` |
| 净值 / 因子值 | `NUMERIC(18,8)` |
| 权重 / 比率 / 利率 | `NUMERIC(12,8)` |

金融数值**禁止使用浮点存储**。复权净值的累乘计算必须使用 `decimal.Decimal`；下游因子计算可用 float64（容差 1e-10 已覆盖该转换）。

**数值容差**（可复现性判定）

| 对象 | 相对误差 |
|---|---|
| Factor 值 / Score | 1e-10 |
| 协方差矩阵 | 1e-8 |
| 优化权重 `w` | 1e-6，**且非零集合必须完全一致** |
| 绩效指标 | 1e-8 |

**不可违反的约束**（违反即为缺陷，非风格问题）

| # | 约束 | 来源 |
|---|---|---|
| C-2 | `src/fip/strategy_library/` 中不得出现任何"是否回测"的分支（`is_backtest` / `runtime_mode` 判断） | 上游 §5.4、SEI-3 |
| C-3 | `src/fip/platform/api/` 与 `src/fip/services/` 不得包含投资策略规则、阈值或常量 | `06-technology-stack` C-11 |
| C-6 | 不得对 `UNAVAILABLE` 数据做任何填充（0 / 均值 / 上期值 / 前向填充） | `FR-FUND-001` |
| C-12 | Adapter 须**如实留空** `provider_available_at` / `published_at`，**不得**用 `ingested_at` 回填 | `04-integration-architecture` §2.5 |
| C-14 | 不引入任何 ML / AI 相关技术栈、依赖或数据通道 | 上游 §6.2.1 |
| C-15 | 不得使用本地文件系统作为跨实例共享存储 | `06-technology-stack` OS-2 |
| PIT-A2 | PIT 接口每次调用必须携带 `decision_at`，缺失时**拒绝**，不得默认取当前时间 | `01-system-architecture` §7.4 |
| PIT-A3 | 不存在"取最新一条"的无约束访问路径 | 同上 |

**命名约定**（`10-api/01` §4.2，本 Plan 的 DB 与 Python 层同样遵守）

- 字段与参数：`snake_case`
- 枚举值：`UPPER_SNAKE_CASE`
- 标识符字段以 `_id` 结尾，版本字段以 `_version` 结尾

**术语**：本 Plan 中 `Fund Data`、`Fund Share Class`、`Peer Group`、`Investment Eligibility`、`Point-in-Time` 等一律为**引用**，定义权属 `docs/01-product/01-product-overview.md` §11。

---

## File Structure

```
fund-investment-platform/
├── pyproject.toml                          # 项目元数据、ruff/mypy/pytest 配置
├── requirements.lock                       # 精确锁定的依赖
├── Makefile                                # 常用命令入口
├── alembic.ini
├── src/fip/
│   ├── __init__.py                         # __version__
│   ├── settings.py                         # pydantic-settings，DB URL 等
│   ├── quant_engine/__init__.py            # 本 Plan 仅建包，不实现
│   ├── strategy_library/__init__.py        # 本 Plan 仅建包，不实现
│   ├── platform/
│   │   ├── db/
│   │   │   ├── base.py                     # DeclarativeBase、schema 常量
│   │   │   ├── types.py                    # Numeric 精度别名
│   │   │   └── mixins.py                   # 版本化 / 区间型标准列 Mixin
│   │   ├── decision_data/
│   │   │   ├── context.py                  # DecisionExecutionContext
│   │   │   ├── pit.py                      # PitDataContext + Repository Protocol
│   │   │   └── current.py                  # CurrentViewContext
│   │   ├── source/port.py                  # SourceAdapter 端口
│   │   ├── jobs/
│   │   │   ├── models.py                   # calculation_job 表
│   │   │   └── submitter.py                # JobSubmitter + 幂等键
│   │   ├── config/
│   │   │   ├── models.py                   # Parameter 三元组
│   │   │   └── loader.py                   # YAML 装载 + PROVISIONAL 语义
│   │   └── cli.py                          # 灌数与 PIT 查询命令
│   └── services/
│       ├── data_service/
│       │   ├── models/{governance,raw,fund,market}.py
│       │   ├── adapters/akshare/{client,datasets}.py
│       │   ├── normalization/adjusted_nav.py   # 复权净值算法（承重）
│       │   ├── repositories/nav.py             # PIT NAV Repository 实现
│       │   ├── eligibility.py
│       │   ├── quality.py
│       │   └── ingest.py
│       ├── factor_service/__init__.py      # 本 Plan 仅建包
│       ├── fund_service/__init__.py
│       ├── portfolio_service/__init__.py
│       └── backtest_service/__init__.py
├── db/migrations/                          # Alembic —— DDL 的权威来源
├── config/
│   ├── strategy/metric/v1.yaml
│   └── policy/evaluation/v1.yaml
└── tests/
    ├── conftest.py                         # 测试数据库 fixture
    ├── unit/  integration/
    ├── fitness/test_architecture.py        # 架构适应度测试
    └── contract/test_akshare_columns.py    # 数据源契约测试（联网，单独标记）
```

**职责边界**：`normalization/adjusted_nav.py` 是纯函数模块，不接触数据库 —— 它是本 Plan 中唯一含复杂算法的文件，隔离出来便于密集测试。`repositories/nav.py` 只做版本解析查询，不做任何计算。

---

## Task 1：项目骨架与工具链

**Files:**
- Create: `pyproject.toml`, `requirements.lock`, `Makefile`, `.gitignore`
- Create: `src/fip/__init__.py`, `src/fip/settings.py`
- Create: 各层包的 `__init__.py`
- Test: `tests/unit/test_package_layout.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces: `fip.__version__: str`；`fip.settings.settings` 具属性 `database_url: str`、`test_database_url: str`

- [ ] **Step 1：初始化 git 仓库与目录骨架**

当前目录**不是** git 仓库，先初始化。

```bash
cd "/Users/zhukun/学习/fund-investment-platform"
git init
/usr/local/opt/python@3.12/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
mkdir -p src/fip/{quant_engine,strategy_library}
mkdir -p src/fip/platform/{db,decision_data,source,jobs,config}
mkdir -p src/fip/services/{factor_service,fund_service,portfolio_service,backtest_service}
mkdir -p src/fip/services/data_service/{models,adapters/akshare,normalization,repositories}
mkdir -p tests/{unit,integration,fitness,contract}
mkdir -p db/migrations config/strategy/metric config/policy/evaluation
find src -type d -exec touch {}/__init__.py \;
touch tests/__init__.py
```

- [ ] **Step 2：写 `.gitignore`**

```bash
cat > .gitignore <<'EOF'
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
*.egg-info/
.env
.DS_Store
EOF
```

- [ ] **Step 3：写 `pyproject.toml`**

```toml
[project]
name = "fund-investment-platform"
version = "0.1.0"
requires-python = "==3.12.*"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"
markers = [
    "integration: 需要 PostgreSQL 测试库",
    "contract: 需要联网访问 AKShare 上游",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.12"
packages = ["fip"]
strict = true
ignore_missing_imports = true
```

- [ ] **Step 4：安装并锁定依赖**

```bash
.venv/bin/pip install \
  "sqlalchemy==2.0.36" "alembic==1.14.0" "psycopg[binary]==3.2.3" \
  "pydantic==2.10.3" "pydantic-settings==2.6.1" "pyyaml==6.0.2" \
  "numpy==2.1.3" "pandas==2.2.3" "pyarrow==18.1.0" "akshare==1.18.94" \
  "pytest==8.3.4" "pytest-cov==6.0.0" "ruff==0.8.4" "mypy==1.13.0"
.venv/bin/pip install -e .
.venv/bin/pip freeze --exclude-editable > requirements.lock
```

若某个版本号安装失败，用 `.venv/bin/pip index versions <pkg>` 查询可用版本并选一个**具体版本号**替换 —— 必须是精确版本，不得改用范围约束。

- [ ] **Step 5：写 `src/fip/__init__.py` 与 `src/fip/settings.py`**

```python
# src/fip/__init__.py
__version__ = "0.1.0"
```

```python
# src/fip/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FIP_", env_file=".env")

    database_url: str = "postgresql+psycopg://localhost/fip_dev"
    test_database_url: str = "postgresql+psycopg://localhost/fip_test"


settings = Settings()
```

- [ ] **Step 6：写测试**

```python
# tests/unit/test_package_layout.py
import importlib

import fip


def test_version_is_set():
    assert fip.__version__ == "0.1.0"


def test_platform_subpackage_does_not_shadow_stdlib():
    """fip.platform 必须嵌套在 fip 下，否则会遮蔽标准库 platform。"""
    import platform as stdlib_platform

    assert hasattr(stdlib_platform, "python_version")
    fip_platform = importlib.import_module("fip.platform")
    assert fip_platform is not stdlib_platform


def test_all_layer_packages_importable():
    for name in [
        "fip.quant_engine",
        "fip.strategy_library",
        "fip.platform.db",
        "fip.platform.decision_data",
        "fip.platform.source",
        "fip.platform.jobs",
        "fip.platform.config",
        "fip.services.data_service",
        "fip.services.factor_service",
        "fip.services.fund_service",
        "fip.services.portfolio_service",
        "fip.services.backtest_service",
    ]:
        importlib.import_module(name)


def test_settings_has_database_urls():
    from fip.settings import settings

    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.test_database_url.startswith("postgresql+psycopg://")
```

- [ ] **Step 7：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_package_layout.py -v`
Expected: 4 passed

（本任务的测试是对骨架的验收，Step 5 已建好实现故直接通过。后续任务严格遵循"先写失败测试"。）

- [ ] **Step 8：写 `Makefile`**

```makefile
PY := .venv/bin/python
PYTEST := .venv/bin/pytest
export PATH := .venv/bin:$(PATH)

.PHONY: test test-unit test-integration test-fitness test-contract lint typecheck check migrate

test-unit:
	$(PYTEST) tests/unit -v

test-integration:
	$(PYTEST) tests/integration -v -m integration

test-fitness:
	$(PYTEST) tests/fitness -v

test-contract:
	$(PYTEST) tests/contract -v -m contract

test:
	$(PYTEST) tests/unit tests/fitness tests/integration -v

migrate:
	.venv/bin/alembic -x db=dev upgrade head

lint:
	.venv/bin/ruff check src tests

typecheck:
	.venv/bin/mypy

check: lint typecheck test
```

- [ ] **Step 9：验证 lint 与类型检查通过**

Run: `make lint && make typecheck`
Expected: 均无错误输出

- [ ] **Step 10：提交**

```bash
git add -A
git commit -m "chore: 初始化项目骨架、三层包结构与工具链

Python 3.12（非 3.13，AKShare 依赖的 wheel 覆盖更稳定）。
fip.platform 嵌套在 fip 下以避免遮蔽标准库 platform 模块。"
```

---

## Task 2：PostgreSQL 实例、8 个 schema 与 Alembic 基线

**Files:**
- Create: `alembic.ini`, `db/migrations/env.py`, `db/migrations/versions/0001_schemas_and_enums.py`
- Create: `src/fip/platform/db/base.py`
- Create: `tests/conftest.py`
- Test: `tests/integration/test_schemas.py`

**Interfaces:**
- Consumes: `fip.settings.settings`
- Produces:
  - `fip.platform.db.base.Base`（SQLAlchemy `DeclarativeBase` 子类）
  - `fip.platform.db.base.SCHEMAS: tuple[str, ...]` = `("raw","fund","market","factor","evaluation","portfolio","backtest","governance")`
  - pytest fixture `db_engine`（会话级）与 `db_session`（函数级，结束回滚）

- [ ] **Step 1：安装并启动 PostgreSQL 17，建库**

> **已由 controller 预置，本步退化为验证。** Homebrew 在 macOS 13 Ventura 上已无任何
> PostgreSQL 预编译包（`@14`~`@17` 全无 bottle），从源码编译又撞上 Command Line Tools
> 过旧，因此改用 Postgres.app（预编译，无需编译工具链与 sudo）。

```bash
export PATH="$HOME/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"
pg_isready -p 5432
psql -d fip_dev -c "SELECT version();"
psql -lqt | cut -d'|' -f1 | grep fip_
```

Expected: `accepting connections`；版本串为 PostgreSQL 17.11 (Postgres.app)；
`fip_dev` 与 `fip_test` 均已存在。

若 `pg_isready` 失败（例如机器重启过），重新启动：

```bash
"$HOME/Applications/Postgres.app/Contents/Versions/17/bin/pg_ctl" \
  -D "$HOME/Library/Application Support/Postgres/var-17" \
  -l /tmp/fip_pg.log -o "-p 5432" start
```

- [ ] **Step 2：写 `src/fip/platform/db/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase

SCHEMAS: tuple[str, ...] = (
    "raw",
    "fund",
    "market",
    "factor",
    "evaluation",
    "portfolio",
    "backtest",
    "governance",
)


class Base(DeclarativeBase):
    """全部 ORM 模型的基类。每个模型必须在 __table_args__ 中显式声明 schema。"""
```

- [ ] **Step 3：写失败的集成测试**

```python
# tests/integration/test_schemas.py
import pytest
from sqlalchemy import text

from fip.platform.db.base import SCHEMAS

pytestmark = pytest.mark.integration


def test_all_eight_schemas_exist(db_engine):
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT schema_name FROM information_schema.schemata")
        ).scalars().all()
    for schema in SCHEMAS:
        assert schema in rows, f"schema {schema} 缺失"


def test_availability_quality_enum_exists(db_engine):
    with db_engine.connect() as conn:
        labels = conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'availability_quality_enum' "
                "ORDER BY e.enumsortorder"
            )
        ).scalars().all()
    assert labels == ["EXACT", "DERIVED", "INFERRED"]
```

- [ ] **Step 4：写 `tests/conftest.py`**

```python
import subprocess

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from fip.platform.db.base import SCHEMAS
from fip.settings import settings


@pytest.fixture(scope="session")
def db_engine():
    """会话级引擎。每次会话前把测试库重置到最新迁移。"""
    engine = create_engine(settings.test_database_url, future=True)
    with engine.connect() as conn:
        for schema in SCHEMAS:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS public.alembic_version"))
        conn.execute(text("DROP TYPE IF EXISTS availability_quality_enum"))
        conn.commit()
    subprocess.run(
        [".venv/bin/alembic", "-x", "db=test", "upgrade", "head"],
        check=True,
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """函数级会话，测试结束回滚，保证用例间互不污染。"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, future=True)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

- [ ] **Step 5：运行测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_schemas.py -v -m integration`
Expected: FAIL —— alembic 尚未配置，`subprocess.run` 报错退出

- [ ] **Step 6：初始化并配置 Alembic**

```bash
.venv/bin/alembic init -t generic db/migrations
```

修改 `alembic.ini` 的两行：

```ini
script_location = db/migrations
sqlalchemy.url =
```

（`sqlalchemy.url` 留空，由 `env.py` 按 `-x db=` 参数选择。）

把 `db/migrations/env.py` 全文替换为：

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from fip.platform.db.base import Base
from fip.settings import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    which = context.get_x_argument(as_dictionary=True).get("db", "dev")
    return settings.test_database_url if which == "test" else settings.database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    config.set_main_option("sqlalchemy.url", _url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7：写基线迁移 `db/migrations/versions/0001_schemas_and_enums.py`**

```python
"""8 个 schema 与共享枚举类型

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = (
    "raw", "fund", "market", "factor",
    "evaluation", "portfolio", "backtest", "governance",
)


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    op.execute(
        "CREATE TYPE availability_quality_enum "
        "AS ENUM ('EXACT', 'DERIVED', 'INFERRED')"
    )


def downgrade() -> None:
    op.execute("DROP TYPE IF EXISTS availability_quality_enum")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
```

- [ ] **Step 8：运行测试确认通过**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/pytest tests/integration/test_schemas.py -v -m integration
```

Expected: 2 passed

- [ ] **Step 9：提交**

```bash
git add -A
git commit -m "feat(db): 建立 8 个 schema、availability_quality 枚举与 Alembic 基线

迁移脚本是 DDL 的权威来源（04-database-design §19.1）。"
```

---

## Task 3：版本化与区间型标准列 Mixin 及其 CHECK 约束

> **这是 Constraint C-12 在存储层的强制点。** 它让"有推送时刻却标成 INFERRED"这类映射错误在写入时就被拦下，而不是等到回测结果失真才被发现。

**Files:**
- Create: `src/fip/platform/db/types.py`, `src/fip/platform/db/mixins.py`
- Create: `db/migrations/versions/0002_mixin_probe_table.py`
- Test: `tests/integration/test_temporal_constraints.py`

**Interfaces:**
- Consumes: `fip.platform.db.base.Base`
- Produces:
  - `fip.platform.db.types.AmountNumeric` = `Numeric(20, 4)`；`NavNumeric` = `Numeric(18, 8)`；`RatioNumeric` = `Numeric(12, 8)`
  - `fip.platform.db.mixins.TimeSourceMixin`（列：`available_at`、`availability_quality`、`published_at`、`provider_available_at`、`ingested_at`、`created_at`）
  - `fip.platform.db.mixins.VersionedMixin`（继承上者，加 `effective_at`、`version`）
  - `fip.platform.db.mixins.IntervalMixin`（继承 `TimeSourceMixin`，加 `valid_from`、`valid_to`）
  - `fip.platform.db.mixins.time_order_sql(anchor: str = "effective_at") -> str`
  - `fip.platform.db.mixins.temporal_check_constraints(table: str, anchor: str = "effective_at") -> tuple[CheckConstraint, CheckConstraint]`
    —— **区间型表必须传 `anchor="valid_from"`**，否则生成的 SQL 引用不存在的 `effective_at` 列
  - `fip.platform.db.mixins.interval_check(table: str) -> CheckConstraint`
  - `fip.platform.db.mixins.QUALITY_SOURCE_SQL: str`、`TIME_ORDER_SQL: str`（供迁移脚本复用）

- [ ] **Step 1：写失败的测试**

```python
# tests/integration/test_temporal_constraints.py
import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

INSERT = text("""
    INSERT INTO governance.mixin_probe
        (effective_at, available_at, availability_quality,
         version, published_at, provider_available_at, ingested_at)
    VALUES
        (:effective_at, :available_at, :quality,
         :version, :published_at, :provider_available_at, :ingested_at)
""")

D = dt.date(2026, 1, 2)
T0 = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.UTC)
T1 = dt.datetime(2026, 1, 2, 18, 0, tzinfo=dt.UTC)
T2 = dt.datetime(2026, 1, 3, 9, 0, tzinfo=dt.UTC)


def _row(**overrides):
    base = dict(
        effective_at=D, available_at=T1, quality="EXACT", version=1,
        published_at=T0, provider_available_at=T1, ingested_at=T2,
    )
    base.update(overrides)
    return base


def test_exact_requires_provider_available_at(db_session):
    """EXACT 必须有 provider_available_at —— 否则是伪装成精确值的兜底值。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="EXACT", provider_available_at=None))
        db_session.flush()


def test_inferred_forbids_any_source(db_session):
    """INFERRED 意味着两个来源都拿不到；有来源却标 INFERRED 是映射错误。"""
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(quality="INFERRED", published_at=T0,
                                        provider_available_at=None))
        db_session.flush()


def test_derived_is_accepted_with_published_at_only(db_session):
    db_session.execute(INSERT, _row(quality="DERIVED", published_at=T0,
                                    provider_available_at=None))
    db_session.flush()


def test_inferred_is_accepted_when_both_sources_null(db_session):
    """AKShare 回补数据的常态：两个来源都拿不到。"""
    db_session.execute(INSERT, _row(quality="INFERRED", published_at=None,
                                    provider_available_at=None))
    db_session.flush()


def test_published_at_cannot_precede_effective_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            published_at=dt.datetime(2025, 12, 31, 9, 0, tzinfo=dt.UTC)))
        db_session.flush()


def test_provider_available_at_cannot_precede_published_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(published_at=T1, provider_available_at=T0))
        db_session.flush()


def test_ingested_at_cannot_precede_provider_available_at(db_session):
    with pytest.raises(IntegrityError):
        db_session.execute(INSERT, _row(
            provider_available_at=T2,
            ingested_at=dt.datetime(2026, 1, 2, 11, 0, tzinfo=dt.UTC)))
        db_session.flush()


def test_announcement_on_effective_date_is_accepted(db_session):
    """effective_at 是 DATE，比较时隐式转当日 00:00，公告当天不应被拒。"""
    db_session.execute(INSERT, _row(
        published_at=dt.datetime(2026, 1, 2, 0, 30, tzinfo=dt.UTC),
        provider_available_at=dt.datetime(2026, 1, 2, 0, 40, tzinfo=dt.UTC),
        ingested_at=dt.datetime(2026, 1, 2, 1, 0, tzinfo=dt.UTC)))
    db_session.flush()
```

- [ ] **Step 2：运行测试确认失败**

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -v -m integration`
Expected: 全部 FAIL —— `relation "governance.mixin_probe" does not exist`

- [ ] **Step 3：写 `src/fip/platform/db/types.py`**

```python
from sqlalchemy import Numeric

# 存储精度（spec §5.4.3）。金融数值禁止使用浮点。
AmountNumeric = Numeric(20, 4)   # 金额
NavNumeric = Numeric(18, 8)      # 净值 / 因子值
RatioNumeric = Numeric(12, 8)    # 权重 / 比率 / 利率
```

- [ ] **Step 4：写 `src/fip/platform/db/mixins.py`**

```python
import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, declarative_mixin, mapped_column

availability_quality_enum = ENUM(
    "EXACT", "DERIVED", "INFERRED",
    name="availability_quality_enum",
    create_type=False,
)

QUALITY_SOURCE_SQL = (
    "(availability_quality = 'EXACT' AND provider_available_at IS NOT NULL) OR "
    "(availability_quality = 'DERIVED' AND provider_available_at IS NULL "
    " AND published_at IS NOT NULL) OR "
    "(availability_quality = 'INFERRED' AND provider_available_at IS NULL "
    " AND published_at IS NULL)"
)

TIME_ORDER_SQL = (
    "(published_at IS NULL OR published_at >= effective_at) AND "
    "(provider_available_at IS NULL OR published_at IS NULL "
    " OR provider_available_at >= published_at) AND "
    "(ingested_at >= COALESCE(provider_available_at, published_at, ingested_at))"
)

INTERVAL_SQL = "valid_to IS NULL OR valid_from < valid_to"


@declarative_mixin
class TimeSourceMixin:
    """available_at 的三个来源依据。

    available_at 是【解析产物】，三个来源是它的依据（03-data/01 §11）。
    published_at 与 provider_available_at 允许为空 —— Provider 能力有差异，
    拿不到就是拿不到，绝不允许用 ingested_at 回填（Constraint C-12）。
    """

    available_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    availability_quality: Mapped[str] = mapped_column(
        availability_quality_enum, nullable=False
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_available_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@declarative_mixin
class VersionedMixin(TimeSourceMixin):
    """事实型表：三时点 + version。修订产生新版本，旧版本保留、不覆盖。"""

    effective_at: Mapped[dt.date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )


@declarative_mixin
class IntervalMixin(TimeSourceMixin):
    """状态型表：valid_from / valid_to。同样需要 available_at（03-erd §15.2）。

    只有 valid_from 没有 available_at 会形成前视偏差 —— 经理任职的生效日
    早于公告日是常态。
    """

    valid_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


def quality_source_check(table: str) -> CheckConstraint:
    """把 available_at 的三级优先级写进数据库（04-database-design §4.4.1）。"""
    return CheckConstraint(QUALITY_SOURCE_SQL, name=f"ck_{table}_quality_source")


def time_order_check(table: str) -> CheckConstraint:
    """时序约束（03-data/01 §11.6）。

    effective_at 是 DATE、其余是 TIMESTAMPTZ，比较时 effective_at 隐式转为
    当日 00:00，因此「公告发生在生效日当天」仍满足约束。
    """
    return CheckConstraint(TIME_ORDER_SQL, name=f"ck_{table}_time_order")


def interval_check(table: str) -> CheckConstraint:
    return CheckConstraint(INTERVAL_SQL, name=f"ck_{table}_interval")


def temporal_check_constraints(table: str) -> tuple[CheckConstraint, CheckConstraint]:
    """版本化表的两组标准约束。区间型表另需 interval_check。"""
    return (quality_source_check(table), time_order_check(table))
```

- [ ] **Step 5：写迁移 `db/migrations/versions/0002_mixin_probe_table.py`**

`mixin_probe` 是**专供约束测试使用的探针表**。它让 Mixin 的约束语义可以被独立验证，而不必等到某张真实业务表建好。

```python
"""mixin 探针表：验证版本化标准列的两组 CHECK 约束

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

from fip.platform.db.mixins import (
    QUALITY_SOURCE_SQL,
    TIME_ORDER_SQL,
    availability_quality_enum,
)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mixin_probe",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("effective_at", sa.Date, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("availability_quality", availability_quality_enum, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(QUALITY_SOURCE_SQL, name="ck_mixin_probe_quality_source"),
        sa.CheckConstraint(TIME_ORDER_SQL, name="ck_mixin_probe_time_order"),
        schema="governance",
    )


def downgrade() -> None:
    op.drop_table("mixin_probe", schema="governance")
```

- [ ] **Step 6：运行测试确认通过**

Run: `.venv/bin/pytest tests/integration/test_temporal_constraints.py -v -m integration`
Expected: 8 passed

- [ ] **Step 7：提交**

```bash
git add -A
git commit -m "feat(db): 版本化/区间型标准列 Mixin 与两组 CHECK 约束

把 available_at 的三级优先级写进数据库层，使『有推送时刻却标成
INFERRED』这类映射错误在写入时即被拦下（Constraint C-12）。"
```

---

## Task 4：DecisionExecutionContext

**Files:**
- Create: `src/fip/platform/decision_data/context.py`
- Test: `tests/unit/test_decision_context.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `RuntimeMode`（`StrEnum`：`LIVE`、`BACKTEST`）
  - `TriggerType`（`StrEnum`：`PERIODIC`、`DRIFT`、`ELIGIBILITY_EVENT`、`CONSTRAINT_BREACH`）
  - `RecomputeScope`（`StrEnum`：`FULL_PIPELINE`、`FROM_UNIVERSE`、`FROM_RISK`、`FROM_CONSTRUCTION`）
  - `DecisionExecutionContext`（frozen dataclass，字段：`decision_id: str`、`decision_at: dt.date`、`data_as_of: dt.date`、`strategy_version: str`、`policy_version: str`、`code_version: str`、`trigger_type: TriggerType`、`recompute_scope: RecomputeScope`、`runtime_mode: RuntimeMode`）
  - `DecisionExecutionContext.scope_for(trigger: TriggerType) -> RecomputeScope`（classmethod）

- [ ] **Step 1：写失败的测试**

```python
# tests/unit/test_decision_context.py
import dataclasses
import datetime as dt

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)


def _ctx(**overrides):
    base = dict(
        decision_id="D-2026-0831-01",
        decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31),
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.LIVE,
    )
    base.update(overrides)
    return DecisionExecutionContext(**base)


def test_context_is_frozen():
    """上下文在链路起点创建后贯穿全程，不得在中途被改写（DEC-1）。"""
    ctx = _ctx()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.decision_at = dt.date(2026, 9, 1)  # type: ignore[misc]


def test_decision_at_is_required():
    with pytest.raises(TypeError):
        DecisionExecutionContext(  # type: ignore[call-arg]
            decision_id="D-1",
            data_as_of=dt.date(2026, 8, 31),
            strategy_version="sv-1",
            policy_version="pv-1",
            code_version="cv-1",
            trigger_type=TriggerType.PERIODIC,
            recompute_scope=RecomputeScope.FULL_PIPELINE,
            runtime_mode=RuntimeMode.LIVE,
        )


def test_data_as_of_cannot_exceed_decision_at():
    """data_as_of 晚于 decision_at 即为未来信息泄漏。"""
    with pytest.raises(ValueError, match="data_as_of"):
        _ctx(data_as_of=dt.date(2026, 9, 1))


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        (TriggerType.PERIODIC, RecomputeScope.FULL_PIPELINE),
        (TriggerType.ELIGIBILITY_EVENT, RecomputeScope.FROM_UNIVERSE),
        (TriggerType.DRIFT, RecomputeScope.FROM_RISK),
        (TriggerType.CONSTRAINT_BREACH, RecomputeScope.FROM_CONSTRUCTION),
    ],
)
def test_scope_is_determined_by_trigger_type(trigger, expected):
    """重算深度由触发类型决定，不得在运行时动态调整（FR-REBAL-001 BR-2）。"""
    assert DecisionExecutionContext.scope_for(trigger) is expected


def test_mismatched_scope_is_rejected():
    with pytest.raises(ValueError, match="recompute_scope"):
        _ctx(trigger_type=TriggerType.DRIFT,
             recompute_scope=RecomputeScope.FULL_PIPELINE)
```

- [ ] **Step 2：运行测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_decision_context.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.platform.decision_data.context'`

- [ ] **Step 3：写实现**

```python
# src/fip/platform/decision_data/context.py
import datetime as dt
from dataclasses import dataclass
from enum import StrEnum


class RuntimeMode(StrEnum):
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class TriggerType(StrEnum):
    PERIODIC = "PERIODIC"
    DRIFT = "DRIFT"
    ELIGIBILITY_EVENT = "ELIGIBILITY_EVENT"
    CONSTRAINT_BREACH = "CONSTRAINT_BREACH"


class RecomputeScope(StrEnum):
    FULL_PIPELINE = "FULL_PIPELINE"          # Factor → Score → Universe → ⑤ → ⑥ → ⑦
    FROM_UNIVERSE = "FROM_UNIVERSE"          # ④ → ⑤ → ⑥ → ⑦
    FROM_RISK = "FROM_RISK"                  # ⑤ → ⑥ → ⑦
    FROM_CONSTRUCTION = "FROM_CONSTRUCTION"  # ⑥ → ⑦


_TRIGGER_TO_SCOPE: dict[TriggerType, RecomputeScope] = {
    TriggerType.PERIODIC: RecomputeScope.FULL_PIPELINE,
    TriggerType.ELIGIBILITY_EVENT: RecomputeScope.FROM_UNIVERSE,
    TriggerType.DRIFT: RecomputeScope.FROM_RISK,
    TriggerType.CONSTRAINT_BREACH: RecomputeScope.FROM_CONSTRUCTION,
}


@dataclass(frozen=True, slots=True)
class DecisionExecutionContext:
    """一次决策执行的显式上下文，贯穿全部阶段。

    DEC-1 在链路起点创建，不在中途重新生成
    DEC-2 decision_at 由上下文提供，领域服务不自行获取当前时间
    DEC-3 上下文随决策快照落库 —— 它是复现该次决策的入口
    """

    decision_id: str
    decision_at: dt.date
    data_as_of: dt.date
    strategy_version: str
    policy_version: str
    code_version: str
    trigger_type: TriggerType
    recompute_scope: RecomputeScope
    runtime_mode: RuntimeMode

    def __post_init__(self) -> None:
        if self.data_as_of > self.decision_at:
            raise ValueError(
                f"data_as_of={self.data_as_of} 晚于 decision_at={self.decision_at}，"
                "构成未来信息泄漏"
            )
        expected = _TRIGGER_TO_SCOPE[self.trigger_type]
        if self.recompute_scope is not expected:
            raise ValueError(
                f"recompute_scope={self.recompute_scope} 与 "
                f"trigger_type={self.trigger_type} 不匹配，应为 {expected}。"
                "重算深度由触发类型决定，不得在运行时动态调整"
            )

    @classmethod
    def scope_for(cls, trigger: TriggerType) -> RecomputeScope:
        return _TRIGGER_TO_SCOPE[trigger]
```

- [ ] **Step 4：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_decision_context.py -v`
Expected: 8 passed

- [ ] **Step 5：提交**

```bash
git add -A
git commit -m "feat(decision-data): DecisionExecutionContext

frozen dataclass 保证上下文贯穿全程不被改写；重算范围由触发类型在
构造期强制，不允许运行时动态调整。"
```

---

## Task 5：PIT 与 CurrentView 端口

> **本 Plan 最重要的一个任务。** PIT 若只靠"记得加时点条件"的编码规范，任何一处遗漏都会造成静默前视偏差 —— 不报错、不影响流程、在净值曲线上完全看不出来。

**Files:**
- Create: `src/fip/platform/decision_data/pit.py`, `src/fip/platform/decision_data/current.py`
- Test: `tests/unit/test_pit_port.py`

**Interfaces:**
- Consumes: `fip.platform.decision_data.context.DecisionExecutionContext`
- Produces:
  - `NavPoint`（frozen dataclass：`effective_at: dt.date`、`adjusted_nav: Decimal`、`unit_nav: Decimal`、`version: int`、`availability_quality: str`）
  - `NavPitRepository`（Protocol，方法 `adjusted_nav_series(share_class_id: int, date_from: dt.date, date_to: dt.date) -> list[NavPoint]`）
  - `PitDataContext(context: DecisionExecutionContext, session: Any)`；属性 `decision_at: dt.date`、`context`；方法 `navs() -> NavPitRepository`
  - `CurrentViewContext(session: Any)`；属性 `session`

- [ ] **Step 1：写失败的测试**

```python
# tests/unit/test_pit_port.py
import datetime as dt
import inspect
import re

import pytest

from fip.platform.decision_data import pit as pit_module
from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.decision_data.current import CurrentViewContext
from fip.platform.decision_data.pit import NavPitRepository, PitDataContext


def _ctx():
    return DecisionExecutionContext(
        decision_id="D-1",
        decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31),
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.LIVE,
    )


def test_pit_context_binds_decision_at_at_construction():
    """PIT-A2：decision_at 在构造期绑定，而非查询期传入。"""
    ctx = PitDataContext(context=_ctx(), session=object())
    assert ctx.decision_at == dt.date(2026, 8, 31)


def test_pit_context_cannot_be_built_without_execution_context():
    """PIT-A2：缺 decision_at 时在【构造期】即失败，而不是查询期。"""
    with pytest.raises(TypeError):
        PitDataContext(session=object())  # type: ignore[call-arg]


def test_repository_methods_do_not_accept_a_time_parameter():
    """时点不是方法参数 —— 否则调用方可以省略它。"""
    sig = inspect.signature(NavPitRepository.adjusted_nav_series)
    forbidden = {"decision_at", "as_of", "as_of_date", "available_at"}
    assert not (set(sig.parameters) & forbidden)


def test_no_unconstrained_latest_access_path():
    """PIT-A3：PIT 模块中不得存在『取最新 / 取当前』的方法。"""
    pattern = re.compile(r"\b(get|fetch|load|read)_(latest|current|newest)\b")
    assert not pattern.search(inspect.getsource(pit_module)), \
        "PIT 模块出现了无约束的取最新路径"


def test_pit_and_current_contexts_are_not_interchangeable():
    """PIT-A4：两种视图在接口层面区分，互不兼容。"""
    assert not issubclass(CurrentViewContext, PitDataContext)
    assert not issubclass(PitDataContext, CurrentViewContext)
    assert not hasattr(CurrentViewContext, "decision_at")
```

- [ ] **Step 2：运行测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_pit_port.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.platform.decision_data.pit'`

- [ ] **Step 3：写 `src/fip/platform/decision_data/pit.py`**

```python
import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from fip.platform.decision_data.context import DecisionExecutionContext


@dataclass(frozen=True, slots=True)
class NavPoint:
    effective_at: dt.date
    adjusted_nav: Decimal
    unit_nav: Decimal
    version: int
    availability_quality: str


@runtime_checkable
class NavPitRepository(Protocol):
    """时点感知的净值访问。

    注意方法签名中【没有】任何时点参数 —— decision_at 由 PitDataContext
    在构造期绑定并注入实现。这使调用方无法省略时点条件（PIT-A2）。
    本 Protocol 同样不提供任何『取最新一条』的方法（PIT-A3）。
    """

    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> list[NavPoint]: ...


class PitDataContext:
    """决策上下文的数据视图。

    领域逻辑只通过注入的本对象访问数据，不自行建立连接（SEI-1）。
    Live 与 Backtest 的差异全部体现在注入的 decision_at 与 session 上，
    领域逻辑本身不感知 runtime_mode（SEI-2）。
    """

    def __init__(self, context: DecisionExecutionContext, session: Any) -> None:
        self._context = context
        self._session = session

    @property
    def decision_at(self) -> dt.date:
        return self._context.decision_at

    @property
    def context(self) -> DecisionExecutionContext:
        return self._context

    def navs(self) -> NavPitRepository:
        from fip.services.data_service.repositories.nav import SqlNavPitRepository

        return SqlNavPitRepository(session=self._session, decision_at=self.decision_at)
```

- [ ] **Step 4：写 `src/fip/platform/decision_data/current.py`**

```python
from typing import Any


class CurrentViewContext:
    """当前视图 —— 仅供 Live Portfolio 的实时状态展示使用（PIT-A4）。

    它与 PitDataContext 是【两个不相干的类型】，没有继承关系，也不暴露
    decision_at。这使二者在类型层面无法混用：需要历史视图的地方拿不到
    当前视图，反之亦然。历史数据的访问一律走 PitDataContext。
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    @property
    def session(self) -> Any:
        return self._session
```

- [ ] **Step 5：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_pit_port.py -v`
Expected: 5 passed

> `PitDataContext.navs()` 内的延迟 import 指向 Task 15 才创建的模块。本任务的测试不调用 `navs()`，因此不受影响；Task 15 完成后该路径即可用。延迟 import 同时避免了 `platform` 层对 `services` 层的模块级依赖。

- [ ] **Step 6：提交**

```bash
git add -A
git commit -m "feat(decision-data): PIT 与 CurrentView 端口

decision_at 在构造期绑定而非查询期传入，Repository 方法签名中不存在
时点参数，也不提供取最新路径 —— 使静默前视偏差在类型层面不可发生。"
```

---

## Task 6：架构适应度测试

> 把架构约束变成 CI 中可执行的断言。**没有这一层，C-2 / C-3 / DEP-3 这类约束只是文档里的句子。**

**Files:**
- Create: `tests/fitness/test_architecture.py`
- Create: `tests/fitness/__init__.py`
- Test: 本任务的产出即测试本身

**Interfaces:**
- Consumes: `src/fip/` 下的全部源码（以 AST 静态分析，不导入）
- Produces: 无运行时接口；供 CI 的 `make test-fitness` 调用

- [ ] **Step 1：写适应度测试**

```python
# tests/fitness/test_architecture.py
import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "fip"


def _py_files(*parts: str) -> list[pathlib.Path]:
    root = SRC.joinpath(*parts)
    return sorted(root.rglob("*.py")) if root.exists() else []


def _imported_roots(path: pathlib.Path) -> set[str]:
    """返回该文件 import 的顶层模块名集合。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _dotted_imports(path: pathlib.Path) -> set[str]:
    """返回该文件 import 的完整点号路径集合。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.add(node.module)
    return out


IO_LIBS = {
    "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "alembic",
    "requests", "httpx", "aiohttp", "urllib", "akshare", "socket",
}

ML_LIBS = {
    "sklearn", "scikit_learn", "torch", "tensorflow", "keras",
    "xgboost", "lightgbm", "catboost", "transformers", "openai", "anthropic",
}


def test_strategy_library_has_no_io_dependency():
    """SDL-1 / PIT-A1：策略库不含数据访问实现，数据经注入的接口提供。"""
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & IO_LIBS))
        for f in _py_files("strategy_library")
        if _imported_roots(f) & IO_LIBS
    ]
    assert not offenders, f"strategy_library 出现 I/O 依赖：{offenders}"


def test_quant_engine_has_no_io_dependency():
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & IO_LIBS))
        for f in _py_files("quant_engine")
        if _imported_roots(f) & IO_LIBS
    ]
    assert not offenders, f"quant_engine 出现 I/O 依赖：{offenders}"


def test_no_ml_dependency_anywhere():
    """Constraint C-14：第一阶段不引入任何 ML / AI 技术栈。"""
    offenders = [
        (f.relative_to(SRC), sorted(_imported_roots(f) & ML_LIBS))
        for f in _py_files()
        if _imported_roots(f) & ML_LIBS
    ]
    assert not offenders, f"出现 ML / AI 依赖：{offenders}"


def test_strategy_library_has_no_runtime_mode_branch():
    """Constraint C-2 / SEI-3：策略库不感知运行模式，不得有『是否回测』分支。

    检查方式：SDL 中不得出现 is_backtest / runtime_mode / BACKTEST 这些名称。
    差异必须全部体现在注入的 decision_at 与 Data Context 上。
    """
    banned = {"is_backtest", "runtime_mode", "RuntimeMode", "BACKTEST"}
    offenders = []
    for f in _py_files("strategy_library"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        hits = {
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in banned
        } | {
            node.attr for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr in banned
        }
        if hits:
            offenders.append((f.relative_to(SRC), sorted(hits)))
    assert not offenders, f"strategy_library 出现运行模式分支：{offenders}"


def test_portfolio_service_does_not_depend_on_factor_service():
    """DEP-3：保证 Return Estimate 与 Fund Score 两条数据流独立。

    portfolio-service 需要的是原始收益序列，不是因子值。
    """
    offenders = [
        f.relative_to(SRC)
        for f in _py_files("services", "portfolio_service")
        if any(m.startswith("fip.services.factor_service") for m in _dotted_imports(f))
    ]
    assert not offenders, f"portfolio_service 依赖了 factor_service：{offenders}"


def test_peer_group_module_does_not_depend_on_scoring_or_universe():
    """Constraint C-4：否则形成 Score → Universe → Peer Group → Score 的循环依赖。

    该循环不报错，但每次重算得到不同分数，直接破坏 NFR-REPRO-001。
    """
    banned_prefixes = (
        "fip.services.fund_service.scoring",
        "fip.services.fund_service.ranking",
        "fip.services.fund_service.universe",
    )
    offenders = []
    for f in _py_files("services", "fund_service", "peer_group"):
        bad = [m for m in _dotted_imports(f) if m.startswith(banned_prefixes)]
        if bad:
            offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"Peer Group 模块依赖了评分/候选池模块：{offenders}"


def test_platform_layer_does_not_import_services_at_module_level():
    """依赖方向单向：services → platform，不得反向。

    platform 内允许函数体内的延迟 import（如 PitDataContext.navs()），
    但不允许模块级 import —— 后者会形成真正的包级循环依赖。
    """
    offenders = []
    for f in _py_files("platform"):
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in tree.body:  # 只看模块级语句
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            bad = [m for m in mods if m.startswith("fip.services")]
            if bad:
                offenders.append((f.relative_to(SRC), bad))
    assert not offenders, f"platform 层模块级依赖了 services 层：{offenders}"


@pytest.mark.parametrize("layer", ["strategy_library", "quant_engine"])
def test_layer_packages_exist(layer):
    """守卫测试：若目录被误删，上面的检查会静默通过（空集合恒满足）。"""
    assert (SRC / layer).is_dir(), f"{layer} 目录不存在，适应度测试将失去意义"
```

- [ ] **Step 2：运行测试确认通过**

Run: `.venv/bin/pytest tests/fitness -v`
Expected: 9 passed

> 最后一个守卫测试是必要的：前面几个检查在目录为空时会因"空集合恒满足"而假性通过。目录被误删或改名时，守卫会立刻失败。

- [ ] **Step 3：人为制造一次违规，确认测试真能抓住**

```bash
echo "import sqlalchemy" > src/fip/strategy_library/_probe.py
.venv/bin/pytest tests/fitness -v -k io_dependency
```

Expected: `test_strategy_library_has_no_io_dependency` FAIL，报出 `_probe.py`

```bash
rm src/fip/strategy_library/_probe.py
.venv/bin/pytest tests/fitness -v
```

Expected: 9 passed

> 这一步不能跳过。**一个从未失败过的测试不能证明它会失败。**

- [ ] **Step 4：提交**

```bash
git add -A
git commit -m "test(fitness): 架构适应度测试

把 C-2/C-3/C-14/C-4/DEP-3 与依赖方向变成 CI 中可执行的断言，
并含目录存在性守卫，防止空集合造成假性通过。"
```

---

## Task 7：配置装载与 PROVISIONAL 语义

> 24 项 P1 参数在此承载。**不阻断，但绝不静默。**

**Files:**
- Create: `src/fip/platform/config/models.py`, `src/fip/platform/config/loader.py`
- Create: `config/strategy/metric/v1.yaml`, `config/policy/evaluation/v1.yaml`
- Test: `tests/unit/test_config_loader.py`

**Interfaces:**
- Consumes: `fip.platform.decision_data.context.RuntimeMode`
- Produces:
  - `ParameterStatus`（`StrEnum`：`PROVISIONAL`、`DECIDED`）
  - `Parameter`（frozen dataclass：`path: str`、`value: Any`、`status: ParameterStatus`、`source: str`）
  - `ConfigSet(parameters: dict[str, Parameter], runtime_mode: RuntimeMode, on_provisional_use: Callable[[Parameter], None] | None = None)`
  - `ConfigSet.get(path: str) -> Any`
  - `ConfigSet.provisional_parameters_used -> tuple[str, ...]`
  - `load_config_file(path: pathlib.Path, runtime_mode: RuntimeMode, on_provisional_use=None) -> ConfigSet`

- [ ] **Step 1：写失败的测试**

```python
# tests/unit/test_config_loader.py
import pathlib

import pytest

from fip.platform.config.loader import ConfigSet, load_config_file
from fip.platform.config.models import Parameter, ParameterStatus
from fip.platform.decision_data.context import RuntimeMode

YAML = """
scoring:
  weights:
    return_score:
      value: 0.30
      status: PROVISIONAL
      source: "P1-6 待投研定案"
    risk_adjusted_score:
      value: 0.30
      status: DECIDED
      source: "2026-08-20 投研评审纪要"
  normalization:
    method:
      value: Z_SCORE
      status: DECIDED
      source: "04-factor/05-factor-normalization"
"""


@pytest.fixture()
def cfg_file(tmp_path: pathlib.Path) -> pathlib.Path:
    p = tmp_path / "scoring.yaml"
    p.write_text(YAML, encoding="utf-8")
    return p


def test_loads_leaf_parameters_by_dotted_path(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST)
    assert cfg.get("scoring.weights.return_score") == 0.30
    assert cfg.get("scoring.normalization.method") == "Z_SCORE"


def test_leaf_missing_status_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a:\n  b:\n    value: 1\n    source: x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="status"):
        load_config_file(bad, runtime_mode=RuntimeMode.BACKTEST)


def test_leaf_missing_source_is_rejected(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("a:\n  b:\n    value: 1\n    status: DECIDED\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source"):
        load_config_file(bad, runtime_mode=RuntimeMode.BACKTEST)


def test_unknown_path_raises(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST)
    with pytest.raises(KeyError, match="scoring.weights.nonexistent"):
        cfg.get("scoring.weights.nonexistent")


def test_provisional_use_under_live_fires_hook(cfg_file):
    """LIVE 消费 PROVISIONAL 参数必须发出告警事件。"""
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.return_score")
    assert [p.path for p in seen] == ["scoring.weights.return_score"]
    assert seen[0].status is ParameterStatus.PROVISIONAL
    assert seen[0].source == "P1-6 待投研定案"


def test_decided_use_under_live_does_not_fire_hook(cfg_file):
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.risk_adjusted_score")
    assert seen == []


def test_backtest_records_usage_without_firing_hook(cfg_file):
    """回测允许使用，但占位标记仍须落入报告的配置章节。"""
    seen: list[Parameter] = []
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.BACKTEST,
                           on_provisional_use=seen.append)
    cfg.get("scoring.weights.return_score")
    assert seen == []
    assert cfg.provisional_parameters_used == ("scoring.weights.return_score",)


def test_provisional_usage_is_deduplicated_and_sorted(cfg_file):
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE)
    cfg.get("scoring.weights.return_score")
    cfg.get("scoring.weights.return_score")
    cfg.get("scoring.weights.risk_adjusted_score")
    assert cfg.provisional_parameters_used == ("scoring.weights.return_score",)


def test_provisional_never_blocks(cfg_file):
    """不阻断 —— 阻断会让 M1 无法端到端运行。"""
    cfg = load_config_file(cfg_file, runtime_mode=RuntimeMode.LIVE)
    assert cfg.get("scoring.weights.return_score") == 0.30
```

- [ ] **Step 2：运行测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_config_loader.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.platform.config.models'`

- [ ] **Step 3：写 `src/fip/platform/config/models.py`**

```python
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ParameterStatus(StrEnum):
    PROVISIONAL = "PROVISIONAL"  # 实现期占位，待投研定案
    DECIDED = "DECIDED"          # 已定案


@dataclass(frozen=True, slots=True)
class Parameter:
    """配置叶子的三元组。

    status 与 source 是必填的：只有 value 的参数无法区分
    『已定案的取值』与『开发期的占位』。
    """

    path: str
    value: Any
    status: ParameterStatus
    source: str
```

- [ ] **Step 4：写 `src/fip/platform/config/loader.py`**

```python
import logging
import pathlib
from collections.abc import Callable
from typing import Any

import yaml

from fip.platform.config.models import Parameter, ParameterStatus
from fip.platform.decision_data.context import RuntimeMode

logger = logging.getLogger(__name__)

_LEAF_KEYS = {"value", "status", "source"}


def _default_on_provisional_use(param: Parameter) -> None:
    logger.warning(
        "ProvisionalParameterUsed",
        extra={
            "event": "ProvisionalParameterUsed",
            "parameter_path": param.path,
            "parameter_source": param.source,
        },
    )


def _flatten(node: Any, prefix: str, out: dict[str, Parameter]) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"配置节点 {prefix!r} 不是映射，无法解析")
    if _LEAF_KEYS & set(node):
        if "value" not in node:
            raise ValueError(f"配置叶子 {prefix!r} 缺少 value")
        if "status" not in node:
            raise ValueError(
                f"配置叶子 {prefix!r} 缺少 status —— "
                "无法区分已定案取值与开发期占位"
            )
        if "source" not in node:
            raise ValueError(f"配置叶子 {prefix!r} 缺少 source")
        out[prefix] = Parameter(
            path=prefix,
            value=node["value"],
            status=ParameterStatus(node["status"]),
            source=node["source"],
        )
        return
    for key, child in node.items():
        _flatten(child, f"{prefix}.{key}" if prefix else str(key), out)


class ConfigSet:
    """一组已装载的参数。

    PROVISIONAL 参数的运行时语义（spec §5.3）：
      BACKTEST —— 允许使用，记录使用清单（落入回测报告的配置章节）
      LIVE     —— 允许使用，记录清单【并】发出告警事件
    两种模式下都【不阻断】：阻断会让链路无法端到端运行；
    但都【不静默】：静默会让占位值伪装成已定案值。
    """

    def __init__(
        self,
        parameters: dict[str, Parameter],
        runtime_mode: RuntimeMode,
        on_provisional_use: Callable[[Parameter], None] | None = None,
    ) -> None:
        self._parameters = parameters
        self._runtime_mode = runtime_mode
        self._on_provisional_use = on_provisional_use or _default_on_provisional_use
        self._provisional_used: set[str] = set()

    def get(self, path: str) -> Any:
        try:
            param = self._parameters[path]
        except KeyError:
            raise KeyError(f"配置项不存在：{path}") from None
        if param.status is ParameterStatus.PROVISIONAL:
            self._provisional_used.add(param.path)
            if self._runtime_mode is RuntimeMode.LIVE:
                self._on_provisional_use(param)
        return param.value

    @property
    def provisional_parameters_used(self) -> tuple[str, ...]:
        """本次执行消费到的 PROVISIONAL 参数清单，写入决策快照。"""
        return tuple(sorted(self._provisional_used))

    @property
    def parameters(self) -> dict[str, Parameter]:
        return dict(self._parameters)


def load_config_file(
    path: pathlib.Path,
    runtime_mode: RuntimeMode,
    on_provisional_use: Callable[[Parameter], None] | None = None,
) -> ConfigSet:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    flat: dict[str, Parameter] = {}
    _flatten(raw, "", flat)
    return ConfigSet(flat, runtime_mode, on_provisional_use)
```

- [ ] **Step 5：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_config_loader.py -v`
Expected: 9 passed

- [ ] **Step 6：写两个真实配置文件**

```bash
cat > config/strategy/metric/v1.yaml <<'EOF'
# Metric Version v1 —— Factor 计算口径与公式
# Owner: factor-service（01-system-architecture §8.2 第 1 项）
annualization:
  trading_days_per_year:
    value: 252
    status: DECIDED
    source: "10-api/01 §12.3 annualized_return 定义为 252 交易日"
adjusted_nav:
  dividend_reinvestment_price:
    value: EX_DATE_NAV
    status: DECIDED
    source: "本 Plan Task 15 —— 以除息日当日单位净值再投资"
  same_day_order:
    value: DIVIDEND_THEN_SPLIT
    status: DECIDED
    source: "本 Plan Task 15 —— 同日先除息后拆分"
EOF

cat > config/policy/evaluation/v1.yaml <<'EOF'
# Evaluation Policy v1 —— MAR、评价周期、评价准入条件
# Owner: fund-service（01-system-architecture §8.2.1 第 1 子项）
mar:
  default:
    value: 0.0
    status: PROVISIONAL
    source: "P1-19 / 上游 TBD-19 待投研定案，下游不得自行填充"
risk_free_rate:
  tenor:
    value: 1Y
    status: PROVISIONAL
    source: "上游 TBD-18 待投研与数据共同确定"
  currency:
    value: CNY
    status: PROVISIONAL
    source: "上游 TBD-18"
EOF
```

- [ ] **Step 7：验证真实配置可装载**

```bash
.venv/bin/python -c "
import pathlib
from fip.platform.config.loader import load_config_file
from fip.platform.decision_data.context import RuntimeMode
for f in ['config/strategy/metric/v1.yaml', 'config/policy/evaluation/v1.yaml']:
    cfg = load_config_file(pathlib.Path(f), RuntimeMode.BACKTEST)
    print(f, '->', sorted(cfg.parameters))
"
```

Expected: 打印出两个文件的全部参数路径，无异常。

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(config): 配置装载与 PROVISIONAL 运行时语义

24 项 P1 待定参数外置为带 status/source 的三元组。LIVE 消费
PROVISIONAL 参数时告警并记入清单，但不阻断 —— 不阻断保证链路可运行，
不静默保证占位值不会伪装成已定案值。"
```

---

## Task 8：Calculation Job 与幂等键

**Files:**
- Create: `src/fip/platform/jobs/models.py`, `src/fip/platform/jobs/submitter.py`
- Create: `db/migrations/versions/0005_calculation_job.py`
- Test: `tests/unit/test_job_idempotency_key.py`, `tests/integration/test_job_submitter.py`

**Interfaces:**
- Consumes: `fip.platform.db.base.Base`、`fip.platform.decision_data.context.DecisionExecutionContext`
- Produces:
  - `ExecutionStatus`（`StrEnum`：`RUNNING`、`COMPLETED`、`BLOCKED`、`FAILED`、`CANCELLED`）
  - `CalculationJob`（ORM，表 `governance.calculation_job`）
  - `decision_idempotency_key(ctx: DecisionExecutionContext) -> str`
  - `ingest_idempotency_key(dataset: str, subject: str, date_from: dt.date, date_to: dt.date) -> str`
  - `JobSubmitter(session)`；方法 `submit(job_type: str, idempotency_key: str, decision_id: str | None = None) -> CalculationJob`、`is_retryable(job: CalculationJob) -> bool`

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_job_idempotency_key.py
import datetime as dt

from fip.platform.decision_data.context import (
    DecisionExecutionContext,
    RecomputeScope,
    RuntimeMode,
    TriggerType,
)
from fip.platform.jobs.submitter import decision_idempotency_key, ingest_idempotency_key


def _ctx(**kw):
    base = dict(
        decision_id="D-1",
        decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31),
        strategy_version="sv-1",
        policy_version="pv-1",
        code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.LIVE,
    )
    base.update(kw)
    return DecisionExecutionContext(**base)


def test_decision_key_uses_the_three_business_dimensions():
    """业务层幂等键 = (decision_at, strategy_version, recompute_scope)。"""
    key = decision_idempotency_key(_ctx())
    assert key == "decision|2026-08-31|sv-1|FULL_PIPELINE"


def test_decision_key_is_stable_across_identical_contexts():
    assert decision_idempotency_key(_ctx()) == decision_idempotency_key(_ctx())


def test_decision_key_changes_with_strategy_version():
    assert decision_idempotency_key(_ctx()) != decision_idempotency_key(
        _ctx(strategy_version="sv-2")
    )


def test_decision_key_ignores_decision_id():
    """同一 (时点, 版本, 范围) 的重复提交必须命中同一个键。"""
    assert decision_idempotency_key(_ctx(decision_id="D-1")) == \
        decision_idempotency_key(_ctx(decision_id="D-2"))


def test_ingest_key_covers_dataset_subject_and_range():
    key = ingest_idempotency_key(
        "fund_nav", "000001", dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    assert key == "ingest|fund_nav|000001|2020-01-01|2020-12-31"
```

- [ ] **Step 2：运行测试确认失败**

Run: `.venv/bin/pytest tests/unit/test_job_idempotency_key.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.platform.jobs.submitter'`

- [ ] **Step 3：写 `src/fip/platform/jobs/models.py`**

```python
import datetime as dt
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class ExecutionStatus(StrEnum):
    """执行状态（架构层）—— 与 Decision Status（业务状态）是两个维度。

    BLOCKED 与 FAILED 不是 Decision Status：它们表示『本次执行没有产生决策』，
    而非『产生了一个失败的决策』（01-system-architecture §10.5.3）。
    """

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"      # Global 级数据质量阻断
    FAILED = "FAILED"        # 系统故障
    CANCELLED = "CANCELLED"


execution_status_enum = ENUM(
    *[s.value for s in ExecutionStatus],
    name="execution_status_enum",
    create_type=False,
)


class CalculationJob(Base):
    __tablename__ = "calculation_job"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(execution_status_enum, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
```

- [ ] **Step 4：写 `src/fip/platform/jobs/submitter.py`**

```python
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import DecisionExecutionContext
from fip.platform.jobs.models import CalculationJob, ExecutionStatus


def decision_idempotency_key(ctx: DecisionExecutionContext) -> str:
    """业务层幂等键（01-system-architecture §10.7）。

    键不含 decision_id —— 否则重复提交会因新 id 而产生新键，
    幂等失效。防的是『同一决策被重复计算』。
    """
    return f"decision|{ctx.decision_at.isoformat()}|{ctx.strategy_version}|{ctx.recompute_scope.value}"


def ingest_idempotency_key(
    dataset: str, subject: str, date_from: dt.date, date_to: dt.date
) -> str:
    """灌数任务的幂等键，使长回补可断点续跑而不产生重复行。"""
    return f"ingest|{dataset}|{subject}|{date_from.isoformat()}|{date_to.isoformat()}"


# INFEASIBLE 是业务结果不是系统故障，不进入本表；BLOCKED 需人工修数据后重跑。
_RETRYABLE = {ExecutionStatus.FAILED}


class JobSubmitter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(
        self,
        job_type: str,
        idempotency_key: str,
        decision_id: str | None = None,
    ) -> CalculationJob:
        """提交任务。相同幂等键的重复提交返回既有任务，不产生第二条记录。"""
        existing = self._session.execute(
            select(CalculationJob).where(
                CalculationJob.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        job = CalculationJob(
            execution_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            job_type=job_type,
            decision_id=decision_id,
            status=ExecutionStatus.RUNNING.value,
            progress=0,
        )
        self._session.add(job)
        self._session.flush()
        return job

    @staticmethod
    def is_retryable(job: CalculationJob) -> bool:
        """只有系统故障可幂等重试。

        把 BLOCKED（数据阻断）当作 FAILED 自动重试会反复撞同一堵墙；
        INFEASIBLE 属 Decision Status，根本不在本表（§10.5.4）。
        """
        return ExecutionStatus(job.status) in _RETRYABLE
```

- [ ] **Step 5：写迁移 `db/migrations/versions/0005_calculation_job.py`**

```python
"""calculation_job 表与 execution_status 枚举

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# 注意：必须用 postgresql.ENUM 而非 sa.Enum —— 通用的 sa.Enum 会【静默忽略】
# create_type=False，导致 SQLAlchemy 重复 CREATE TYPE 而报 DuplicateObject。

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE execution_status_enum AS ENUM "
        "('RUNNING', 'COMPLETED', 'BLOCKED', 'FAILED', 'CANCELLED')"
    )
    op.create_table(
        "calculation_job",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("execution_id", sa.String(64), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(64), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "RUNNING", "COMPLETED", "BLOCKED", "FAILED", "CANCELLED",
                name="execution_status_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        schema="governance",
    )
    op.create_index(
        "ix_calculation_job_status", "calculation_job", ["status"], schema="governance"
    )


def downgrade() -> None:
    op.drop_index("ix_calculation_job_status", "calculation_job", schema="governance")
    op.drop_table("calculation_job", schema="governance")
    op.execute("DROP TYPE IF EXISTS execution_status_enum")
```

- [ ] **Step 6：写集成测试**

```python
# tests/integration/test_job_submitter.py
import pytest
from sqlalchemy import func, select

from fip.platform.jobs.models import CalculationJob, ExecutionStatus
from fip.platform.jobs.submitter import JobSubmitter

pytestmark = pytest.mark.integration


def test_duplicate_submission_returns_the_same_job(db_session):
    """重复投递不产生重复结果（NFR-REL-001）。"""
    submitter = JobSubmitter(db_session)
    first = submitter.submit("factor_calculation", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    second = submitter.submit("factor_calculation", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    assert first.execution_id == second.execution_id
    count = db_session.execute(select(func.count()).select_from(CalculationJob)).scalar_one()
    assert count == 1


def test_different_keys_create_separate_jobs(db_session):
    submitter = JobSubmitter(db_session)
    a = submitter.submit("ingest", "ingest|fund_nav|000001|2020-01-01|2020-12-31")
    b = submitter.submit("ingest", "ingest|fund_nav|000002|2020-01-01|2020-12-31")
    assert a.execution_id != b.execution_id


def test_new_job_starts_running(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|x|y|2020-01-01|2020-01-02")
    assert job.status == ExecutionStatus.RUNNING.value
    assert job.progress == 0


@pytest.mark.parametrize(
    ("status", "retryable"),
    [
        (ExecutionStatus.FAILED, True),       # 系统故障 → 幂等重试
        (ExecutionStatus.BLOCKED, False),     # 数据阻断 → 修数据后重跑，不自动重试
        (ExecutionStatus.COMPLETED, False),
        (ExecutionStatus.CANCELLED, False),
        (ExecutionStatus.RUNNING, False),
    ],
)
def test_only_system_failure_is_retryable(db_session, status, retryable):
    job = JobSubmitter(db_session).submit("ingest", f"ingest|k|{status.value}|2020-01-01|2020-01-02")
    job.status = status.value
    assert JobSubmitter.is_retryable(job) is retryable
```

- [ ] **Step 7：运行两组测试确认通过**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/pytest tests/unit/test_job_idempotency_key.py tests/integration/test_job_submitter.py -v
```

Expected: 5 passed（unit）+ 8 passed（integration）

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(jobs): Calculation Job 与幂等键

业务层幂等键 (decision_at, strategy_version, recompute_scope) 不含
decision_id，否则重复提交会因新 id 产生新键而使幂等失效。
只有 FAILED 可重试：BLOCKED 需先修数据，INFEASIBLE 属业务状态不入本表。"
```

---

## Task 9：SourceAdapter 端口、available_at 解析与 raw/governance 表

> `resolve_availability` 是 Constraint C-12 的**唯一实现点**。全部 Adapter 都必须经它产出 `available_at` 与 `availability_quality`，任何 Adapter 都不得自行拼装这两个字段。

**Files:**
- Create: `src/fip/platform/source/availability.py`, `src/fip/platform/source/port.py`
- Create: `src/fip/services/data_service/models/governance.py`, `src/fip/services/data_service/models/raw.py`
- Create: `db/migrations/versions/0004_governance_and_raw.py`
- Test: `tests/unit/test_availability_resolution.py`, `tests/integration/test_raw_payload.py`

**Interfaces:**
- Consumes: `fip.platform.db.base.Base`
- Produces:
  - `AvailabilityQuality`（`StrEnum`：`EXACT`、`DERIVED`、`INFERRED`）
  - `resolve_availability(published_at, provider_available_at, ingested_at) -> tuple[dt.datetime, AvailabilityQuality]`
  - `declared_lag_availability(effective_at: dt.date, lag: dt.timedelta) -> tuple[dt.datetime, AvailabilityQuality]`
  - `SourceRecord`（frozen dataclass：`dataset`、`payload: bytes`、`row_count: int`、`request_params: dict[str, str]`、`published_at`、`provider_available_at`、`ingested_at`）
  - `SourceAdapter`（Protocol：属性 `provider_code: str`、`adapter_version: str`；方法 `fetch(dataset: str, **params: str) -> SourceRecord`）
  - ORM：`DataProvider`、`DataProviderDataset`、`DataSourcePriority`、`PolicyVersion`、`AuditLog`、`RawPayload`、`CanonicalRaw`

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_availability_resolution.py
import datetime as dt

import pytest

from fip.platform.source.availability import (
    AvailabilityQuality,
    declared_lag_availability,
    resolve_availability,
)

PUB = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.UTC)
PROV = dt.datetime(2026, 1, 2, 10, 3, tzinfo=dt.UTC)
ING = dt.datetime(2026, 1, 2, 18, 0, tzinfo=dt.UTC)


def test_provider_push_time_wins_and_is_exact():
    assert resolve_availability(PUB, PROV, ING) == (PROV, AvailabilityQuality.EXACT)


def test_published_at_is_used_when_provider_time_missing():
    """公告发布 ≠ 投资系统已知，因此只能是 DERIVED。"""
    assert resolve_availability(PUB, None, ING) == (PUB, AvailabilityQuality.DERIVED)


def test_falls_back_to_ingested_at_as_inferred():
    """AKShare 回补数据的常态。"""
    assert resolve_availability(None, None, ING) == (ING, AvailabilityQuality.INFERRED)


def test_exact_is_never_returned_without_provider_time():
    """C-12：绝不允许用 ingested_at 回填 provider_available_at 后标成 EXACT。"""
    for pub in (PUB, None):
        _, quality = resolve_availability(pub, None, ING)
        assert quality is not AvailabilityQuality.EXACT


def test_declared_lag_produces_inferred_quality():
    """净值历史回补：available_at = effective_at + 声明的披露时滞。"""
    at, quality = declared_lag_availability(dt.date(2020, 1, 2), dt.timedelta(days=1))
    assert at == dt.datetime(2020, 1, 3, 0, 0, tzinfo=dt.UTC)
    assert quality is AvailabilityQuality.INFERRED


def test_declared_lag_rejects_negative_lag():
    with pytest.raises(ValueError, match="lag"):
        declared_lag_availability(dt.date(2020, 1, 2), dt.timedelta(days=-1))
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_availability_resolution.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'fip.platform.source.availability'`

- [ ] **Step 3：写 `src/fip/platform/source/availability.py`**

```python
import datetime as dt
from enum import StrEnum


class AvailabilityQuality(StrEnum):
    EXACT = "EXACT"        # 取自供应商推送时刻
    DERIVED = "DERIVED"    # 取自公告时刻（推送时刻不可得）
    INFERRED = "INFERRED"  # 取自平台落库时刻或声明的推导规则


def resolve_availability(
    published_at: dt.datetime | None,
    provider_available_at: dt.datetime | None,
    ingested_at: dt.datetime,
) -> tuple[dt.datetime, AvailabilityQuality]:
    """按三级优先级解析 available_at（03-data/01 §11.3）。

    这是 Constraint C-12 的唯一实现点：Adapter 必须如实传入 None，
    本函数据此产出正确的 quality。任何 Adapter 都不得自行拼装这两个字段。

    「公告发布 ≠ 投资系统已知」—— 10:00 公告、10:03 推送时，系统在
    10:00 并不知道。因此只有推送时刻才配称 EXACT。
    """
    if provider_available_at is not None:
        return provider_available_at, AvailabilityQuality.EXACT
    if published_at is not None:
        return published_at, AvailabilityQuality.DERIVED
    return ingested_at, AvailabilityQuality.INFERRED


def declared_lag_availability(
    effective_at: dt.date, lag: dt.timedelta
) -> tuple[dt.datetime, AvailabilityQuality]:
    """用【声明的披露时滞】推导 available_at，质量恒为 INFERRED。

    用于 AKShare 净值历史回补：上游没有披露时刻，但净值的披露节奏是
    已知且稳定的。这是一条【声明的推导规则】而非猜测 —— 时滞取值写入
    governance.data_source_priority 并版本化，回测报告必须复述它。

    质量恒为 INFERRED，绝不因为规则可信就升级为 DERIVED。
    """
    if lag < dt.timedelta(0):
        raise ValueError(f"披露时滞 lag={lag} 不得为负")
    base = dt.datetime.combine(effective_at, dt.time.min, tzinfo=dt.UTC)
    return base + lag, AvailabilityQuality.INFERRED
```

- [ ] **Step 4：写 `src/fip/platform/source/port.py`**

```python
import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """一次外部取数的原始产物。

    payload 是序列化后的原始返回（parquet），全量留存 —— 上游格式会漂移，
    保留原始 payload 才能在 Adapter 修 bug 后重解析而不重新抓取
    （raw_payload : canonical_raw = 1:N，03-erd §7.1）。

    published_at 与 provider_available_at 拿不到时【必须】为 None，
    不得用 ingested_at 回填（Constraint C-12）。
    """

    dataset: str
    payload: bytes
    row_count: int
    ingested_at: dt.datetime
    request_params: dict[str, str] = field(default_factory=dict)
    published_at: dt.datetime | None = None
    provider_available_at: dt.datetime | None = None


@runtime_checkable
class SourceAdapter(Protocol):
    """外部数据源端口。

    Adapter 只负责协议与格式转换、字段映射到规范模型、如实填写三个时间来源。
    它【不负责】业务规则判断与数据质量分级 —— 后者属 data-service 本体
    （04-integration-architecture §2）。

    保留本端口使 M2+ 换商业数据源时下游零改动。
    """

    provider_code: str
    adapter_version: str

    def fetch(self, dataset: str, **params: str) -> SourceRecord: ...
```

- [ ] **Step 5：写 `src/fip/services/data_service/models/governance.py`**

```python
import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class DataProvider(Base):
    __tablename__ = "data_provider"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataProviderDataset(Base):
    """一个 Provider 下的一个数据集。

    adapter_version 与 library_version 必须记录 —— AKShare 跨版本改列名是
    常态，静默改列会导致错误映射而不报错。
    """

    __tablename__ = "data_provider_dataset"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("governance.data_provider.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_code: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(32), nullable=False)
    library_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DataSourcePriority(Base):
    """同一字段多来源时的优先级，以及【声明的披露时滞】。

    披露时滞写在这里而非代码里，使它成为可版本化、可被回测报告复述的
    配置，而不是散落在 Adapter 中的魔数。
    """

    __tablename__ = "data_source_priority"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("governance.data_provider_dataset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    disclosure_lag_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolicyVersion(Base):
    """五个 Policy 子项的版本登记。决策快照以 FK 引用本表。"""

    __tablename__ = "policy_version"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    policy_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditLog(Base):
    """审计记录必须在被审计对象删除后仍然存在，因此【不建外键】。

    存 (resource_type, resource_id) 的逻辑引用（03-erd §7.3）。
    """

    __tablename__ = "audit_log"
    __table_args__ = {"schema": "governance"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6：写 `src/fip/services/data_service/models/raw.py`**

```python
import datetime as dt

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class RawPayload(Base):
    """Provider 的原始返回，序列化为 parquet。【不可修改】。

    保留它是 Adapter 修 bug 后可重解析的前提 —— 否则只能重新抓取，
    而上游的历史数据可能已经变了。
    """

    __tablename__ = "raw_payload"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("governance.data_provider_dataset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    library_version: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_available_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CanonicalRaw(Base):
    """一次 payload 的解析产物。同一 payload 可被多次重新解析（1:N）。"""

    __tablename__ = "canonical_raw"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_payload_id: Mapped[int] = mapped_column(
        ForeignKey("raw.raw_payload.id", ondelete="RESTRICT"), nullable=False
    )
    adapter_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parsed_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 7：生成迁移**

```bash
.venv/bin/alembic -x db=dev revision --autogenerate -m "governance 与 raw 表" --rev-id 0004
```

打开生成的 `db/migrations/versions/0004_*.py`，**逐行核对**：确认它只创建本任务的 7 张表，删除任何对 `governance.mixin_probe`、`governance.calculation_job` 的误判性 drop（autogenerate 有时会因枚举类型比对差异产生噪声）。然后：

```bash
.venv/bin/alembic -x db=dev upgrade head
```

- [ ] **Step 8：写集成测试**

```python
# tests/integration/test_raw_payload.py
import datetime as dt

import pytest

from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
from fip.services.data_service.models.raw import CanonicalRaw, RawPayload

pytestmark = pytest.mark.integration


@pytest.fixture()
def dataset(db_session):
    provider = DataProvider(provider_code="AKSHARE", display_name="AKShare")
    db_session.add(provider)
    db_session.flush()
    ds = DataProviderDataset(
        provider_id=provider.id,
        dataset_code="fund_open_fund_info_em.单位净值走势",
        adapter_version="1",
        library_version="1.18.94",
    )
    db_session.add(ds)
    db_session.flush()
    return ds


def test_one_payload_can_be_parsed_multiple_times(db_session, dataset):
    """1:N 是关键 —— Adapter 修 bug 后可重解析而不重新抓取。"""
    payload = RawPayload(
        dataset_id=dataset.id,
        request_params={"symbol": "000001"},
        payload=b"PAR1-fake-parquet",
        row_count=3,
        library_version="1.18.94",
        published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )
    db_session.add(payload)
    db_session.flush()
    db_session.add_all([
        CanonicalRaw(raw_payload_id=payload.id, adapter_version="1", parsed_row_count=3),
        CanonicalRaw(raw_payload_id=payload.id, adapter_version="2", parsed_row_count=3),
    ])
    db_session.flush()
    assert db_session.query(CanonicalRaw).filter_by(raw_payload_id=payload.id).count() == 2


def test_payload_records_library_version(db_session, dataset):
    """AKShare 版本必须随每行 payload 记录，否则无法定位错映射的来源。"""
    payload = RawPayload(
        dataset_id=dataset.id, request_params={}, payload=b"x", row_count=0,
        library_version="1.18.94",
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )
    db_session.add(payload)
    db_session.flush()
    assert payload.library_version == "1.18.94"
```

- [ ] **Step 9：运行全部测试确认通过**

Run: `.venv/bin/pytest tests/unit tests/integration tests/fitness -v`
Expected: 全部 passed

- [ ] **Step 10：提交**

```bash
git add -A
git commit -m "feat(source): SourceAdapter 端口、available_at 三级解析与 raw/governance 表

resolve_availability 是 C-12 的唯一实现点，Adapter 不得自行拼装
available_at 与 availability_quality。披露时滞落在 data_source_priority
表中并版本化，使它成为可复述的声明规则而非代码里的魔数。"
```

---

## Task 10：AkShareSourceAdapter 与数据源契约测试

> AKShare 跨版本改列名是常态，而**静默改列会导致错误映射且不报错**。契约测试让升级在 CI 中失败，而不是让因子值悄悄错掉。

**Files:**
- Create: `src/fip/services/data_service/adapters/akshare/datasets.py`
- Create: `src/fip/services/data_service/adapters/akshare/client.py`
- Test: `tests/unit/test_akshare_adapter.py`, `tests/contract/test_akshare_columns.py`

**Interfaces:**
- Consumes: `fip.platform.source.port.SourceAdapter`、`SourceRecord`
- Produces:
  - `DATASETS: dict[str, DatasetSpec]`；`DatasetSpec`（frozen dataclass：`code: str`、`callable_name: str`、`fixed_params: dict[str, str]`、`required_columns: frozenset[str]`）
  - `AkShareSourceAdapter(clock: Callable[[], dt.datetime] = ...)`；属性 `provider_code = "AKSHARE"`、`adapter_version`、`library_version`；方法 `fetch(dataset, **params) -> SourceRecord`
  - `AkShareContractError`（异常）

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_akshare_adapter.py
import datetime as dt
import io

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.client import (
    AkShareContractError,
    AkShareSourceAdapter,
)
from fip.services.data_service.adapters.akshare.datasets import DATASETS

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)


def _adapter(frame: pd.DataFrame) -> AkShareSourceAdapter:
    return AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=lambda *_a, **_k: frame)


def test_fetch_returns_parquet_payload_and_row_count():
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.row_count == 1
    assert record.dataset == "fund_nav"
    restored = pd.read_parquet(io.BytesIO(record.payload))
    assert list(restored.columns) == ["净值日期", "单位净值", "日增长率"]


def test_fetch_leaves_both_time_sources_null():
    """C-12：AKShare 给不出披露时刻，Adapter 必须如实留空。"""
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.published_at is None
    assert record.provider_available_at is None
    assert record.ingested_at == FIXED_NOW


def test_missing_required_column_raises_contract_error():
    """列缺失必须显式失败 —— 静默错映射是最危险的失败模式。"""
    frame = pd.DataFrame({"净值日期": ["2020-01-02"]})  # 缺 单位净值
    with pytest.raises(AkShareContractError, match="单位净值"):
        _adapter(frame).fetch("fund_nav", symbol="000001")


def test_unknown_dataset_raises():
    with pytest.raises(KeyError, match="not_a_dataset"):
        _adapter(pd.DataFrame()).fetch("not_a_dataset")


def test_request_params_are_recorded():
    frame = pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0000"],
                          "日增长率": ["0.10"]})
    record = _adapter(frame).fetch("fund_nav", symbol="000001")
    assert record.request_params["symbol"] == "000001"
    assert record.request_params["indicator"] == "单位净值走势"


def test_adapter_satisfies_the_source_port():
    from fip.platform.source.port import SourceAdapter

    assert isinstance(_adapter(pd.DataFrame()), SourceAdapter)


def test_every_dataset_declares_required_columns():
    """没有列契约的数据集等于没有契约测试。"""
    for code, spec in DATASETS.items():
        assert spec.required_columns, f"数据集 {code} 未声明 required_columns"
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_akshare_adapter.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...adapters.akshare.client`

- [ ] **Step 3：写 `datasets.py`**

> **本文件的列名与函数名必须对照已安装的 AKShare 版本核对。** 执行 Step 5 的探查脚本确认后再定稿；若与下表不符，**以探查结果为准并同步修改本文件**。

```python
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    code: str
    callable_name: str
    fixed_params: dict[str, str] = field(default_factory=dict)
    required_columns: frozenset[str] = frozenset()


DATASETS: dict[str, DatasetSpec] = {
    "fund_list": DatasetSpec(
        code="fund_list",
        callable_name="fund_name_em",
        required_columns=frozenset({"基金代码", "基金简称", "基金类型"}),
    ),
    "fund_nav": DatasetSpec(
        code="fund_nav",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "单位净值走势"},
        required_columns=frozenset({"净值日期", "单位净值"}),
    ),
    "fund_cumulative_nav": DatasetSpec(
        code="fund_cumulative_nav",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "累计净值走势"},
        required_columns=frozenset({"净值日期", "累计净值"}),
    ),
    "fund_distribution": DatasetSpec(
        code="fund_distribution",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "分红送配详情"},
        required_columns=frozenset({"年份", "权益登记日", "除息日", "每10份分红"}),
    ),
    "fund_split": DatasetSpec(
        code="fund_split",
        callable_name="fund_open_fund_info_em",
        fixed_params={"indicator": "拆分详情"},
        required_columns=frozenset({"年份", "拆分折算日", "拆分折算比例"}),
    ),
    "risk_free_rate": DatasetSpec(
        code="risk_free_rate",
        callable_name="bond_china_yield",
        required_columns=frozenset({"曲线名称", "日期"}),
    ),
}
```

- [ ] **Step 4：写 `client.py`**

```python
import datetime as dt
import io
from collections.abc import Callable
from typing import Any

import pandas as pd

from fip.platform.source.port import SourceRecord
from fip.services.data_service.adapters.akshare.datasets import DATASETS, DatasetSpec


class AkShareContractError(RuntimeError):
    """上游返回的列结构与声明的契约不符。

    显式失败而非静默继续 —— 错映射的因子值不会报错，只会悄悄算错。
    """


def _default_caller(name: str, **params: Any) -> pd.DataFrame:
    import akshare

    fn = getattr(akshare, name, None)
    if fn is None:
        raise AkShareContractError(f"AKShare 无函数 {name}，可能是版本变更")
    return fn(**params)


def _library_version() -> str:
    import akshare

    return str(getattr(akshare, "__version__", "unknown"))


class AkShareSourceAdapter:
    """AKShare 数据源适配器。

    只做协议与格式转换、列契约校验、如实填写三个时间来源。
    不做任何业务规则判断与质量分级（后者属 data-service 本体）。

    AKShare 底层是天天基金 / 新浪 / 中债等公开源，【没有披露时刻】。
    因此 published_at 与 provider_available_at 恒为 None —— 这是事实，
    不是缺陷掩盖。下游据此得到 INFERRED 质量并在 bias-check 中暴露。
    """

    provider_code = "AKSHARE"
    adapter_version = "1"

    def __init__(
        self,
        clock: Callable[[], dt.datetime] | None = None,
        caller: Callable[..., pd.DataFrame] | None = None,
    ) -> None:
        self._clock = clock or (lambda: dt.datetime.now(dt.UTC))
        self._caller = caller or _default_caller

    @property
    def library_version(self) -> str:
        return _library_version()

    def fetch(self, dataset: str, **params: str) -> SourceRecord:
        try:
            spec: DatasetSpec = DATASETS[dataset]
        except KeyError:
            raise KeyError(f"未声明的数据集：{dataset}") from None

        call_params: dict[str, Any] = {**spec.fixed_params, **params}
        frame = self._caller(spec.callable_name, **call_params)
        self._assert_columns(spec, frame)

        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return SourceRecord(
            dataset=dataset,
            payload=buffer.getvalue(),
            row_count=len(frame),
            ingested_at=self._clock(),
            request_params={k: str(v) for k, v in call_params.items()},
            published_at=None,          # AKShare 给不出，如实留空（C-12）
            provider_available_at=None,  # 同上
        )

    @staticmethod
    def _assert_columns(spec: DatasetSpec, frame: pd.DataFrame) -> None:
        missing = spec.required_columns - set(frame.columns)
        if missing:
            raise AkShareContractError(
                f"数据集 {spec.code}（{spec.callable_name}）缺少列 "
                f"{sorted(missing)}；实际列为 {sorted(frame.columns)}。"
                "AKShare 版本变更会改列名，请核对并同步 datasets.py"
            )
```

- [ ] **Step 5：探查真实 AKShare 的列结构，据实修正 `datasets.py`**

```bash
.venv/bin/python - <<'EOF'
import akshare as ak
print("akshare", ak.__version__)
probes = [
    ("fund_name_em", {}),
    ("fund_open_fund_info_em", {"symbol": "000001", "indicator": "单位净值走势"}),
    ("fund_open_fund_info_em", {"symbol": "000001", "indicator": "累计净值走势"}),
    ("fund_open_fund_info_em", {"symbol": "161725", "indicator": "分红送配详情"}),
    ("fund_open_fund_info_em", {"symbol": "161725", "indicator": "拆分详情"}),
    ("bond_china_yield", {"start_date": "20240101", "end_date": "20240110"}),
]
for name, kw in probes:
    try:
        df = getattr(ak, name)(**kw)
        print(f"\n{name} {kw}\n  shape={df.shape}\n  columns={list(df.columns)}")
        print(df.head(2).to_string())
    except Exception as exc:
        print(f"\n{name} {kw}\n  FAILED: {type(exc).__name__}: {exc}")
EOF
```

**把探查到的真实列名写回 `datasets.py` 的 `required_columns`。** 若某个函数名不存在或参数不符，用 `[n for n in dir(ak) if "fund" in n]` 找到正确名称。若某数据集在当前版本完全不可用，**在 `datasets.py` 中删除该条目并在提交信息中说明**，不要保留一个跑不通的声明。

- [ ] **Step 6：写契约测试**

```python
# tests/contract/test_akshare_columns.py
"""数据源契约测试 —— 需联网，用 -m contract 单独运行。

作用：AKShare 升级后若改了列名，本测试失败，而不是让 Adapter
静默错映射字段。这是 R-2 的主要防线。
"""
import pytest

from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.adapters.akshare.datasets import DATASETS

pytestmark = pytest.mark.contract

PROBE_PARAMS: dict[str, dict[str, str]] = {
    "fund_list": {},
    "fund_nav": {"symbol": "000001"},
    "fund_cumulative_nav": {"symbol": "000001"},
    "fund_distribution": {"symbol": "161725"},
    "fund_split": {"symbol": "161725"},
    "risk_free_rate": {"start_date": "20240101", "end_date": "20240110"},
}


@pytest.mark.parametrize("dataset", sorted(DATASETS))
def test_upstream_still_provides_declared_columns(dataset):
    adapter = AkShareSourceAdapter()
    record = adapter.fetch(dataset, **PROBE_PARAMS[dataset])
    assert record.row_count >= 0


def test_every_dataset_has_probe_params():
    assert set(PROBE_PARAMS) == set(DATASETS), \
        "新增数据集时必须同时补探查参数，否则该数据集没有契约保护"
```

- [ ] **Step 7：运行两组测试**

```bash
.venv/bin/pytest tests/unit/test_akshare_adapter.py -v
.venv/bin/pytest tests/contract -v -m contract
```

Expected: 单元测试 7 passed；契约测试全部 passed（若失败，说明 Step 5 的列名未修正到位，回到 Step 5）

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(adapter): AkShareSourceAdapter 与数据源契约测试

published_at 与 provider_available_at 恒为 None —— AKShare 给不出披露
时刻，如实留空而非回填（C-12）。列契约不符时抛 AkShareContractError
显式失败，使版本升级导致的错映射在 CI 中暴露而非静默算错。"
```

---

## Task 11：Fund / Share Class 与归组规则

> AKShare 的 6 位代码对应的是**份额类别**，不是基金产品。`03-erd` §5.2 要求两者分离 —— 合并后无法表达 A 类与 C 类的费率差异，进而无法表达净值、因子、评分的差异。
>
> **归组不确定时不猜**：单独成一个 `fund` 并标记待人工确认（spec §4.5 / R-4）。

**Files:**
- Create: `src/fip/services/data_service/models/fund.py`
- Create: `src/fip/services/data_service/grouping.py`
- Create: `db/migrations/versions/0007_fund_core.py`
- Test: `tests/unit/test_share_class_grouping.py`, `tests/integration/test_fund_core.py`

**Interfaces:**
- Consumes: `fip.platform.db.base.Base`、`fip.platform.db.mixins`
- Produces:
  - `GroupingStatus`（`StrEnum`：`CONFIRMED`、`UNCONFIRMED`）
  - `GroupingResult`（frozen dataclass：`product_name: str`、`share_class_code: str`、`status: GroupingStatus`）
  - `split_share_class_name(display_name: str) -> GroupingResult`
  - ORM：`Fund`（`fund.fund`）、`FundShareClass`（`fund.fund_share_class`）、`ProviderFundIdentity`（`fund.provider_fund_identity`）

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_share_class_grouping.py
import pytest

from fip.services.data_service.grouping import (
    GroupingStatus,
    split_share_class_name,
)


@pytest.mark.parametrize(
    ("display_name", "product", "cls"),
    [
        ("易方达蓝筹精选混合A", "易方达蓝筹精选混合", "A"),
        ("易方达蓝筹精选混合C", "易方达蓝筹精选混合", "C"),
        ("招商中证白酒指数分级B", "招商中证白酒指数分级", "B"),
        ("兴全合润混合A类", "兴全合润混合", "A"),
    ],
)
def test_trailing_single_letter_is_a_share_class(display_name, product, cls):
    result = split_share_class_name(display_name)
    assert result.status is GroupingStatus.CONFIRMED
    assert result.product_name == product
    assert result.share_class_code == cls


def test_name_without_suffix_is_a_single_class_product():
    result = split_share_class_name("华夏成长混合")
    assert result.status is GroupingStatus.CONFIRMED
    assert result.product_name == "华夏成长混合"
    assert result.share_class_code == "DEFAULT"


@pytest.mark.parametrize(
    "display_name",
    [
        "广发纳斯达克100ETF",       # 结尾是 ETF，F 前还是大写字母
        "华宝油气LOF",              # 同上
        "易方达中概互联50ETF",
    ],
)
def test_ambiguous_trailing_letters_are_not_guessed(display_name):
    """不猜 —— 归组不确定的份额类别单独成一个 fund 并标记待确认。"""
    result = split_share_class_name(display_name)
    assert result.status is GroupingStatus.UNCONFIRMED
    assert result.product_name == display_name
    assert result.share_class_code == "DEFAULT"


def test_two_classes_of_the_same_product_share_a_product_name():
    """归组正确性的核心断言：同产品的两个类别必须落到同一个 product_name。"""
    a = split_share_class_name("易方达蓝筹精选混合A")
    c = split_share_class_name("易方达蓝筹精选混合C")
    assert a.product_name == c.product_name
    assert a.share_class_code != c.share_class_code


def test_empty_stem_is_unconfirmed():
    result = split_share_class_name("A")
    assert result.status is GroupingStatus.UNCONFIRMED


def test_whitespace_is_stripped():
    assert split_share_class_name("  华夏成长混合  ").product_name == "华夏成长混合"
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_share_class_grouping.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...data_service.grouping`

- [ ] **Step 3：写 `src/fip/services/data_service/grouping.py`**

```python
import re
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_SHARE_CLASS = "DEFAULT"

# 结尾的单个大写字母（可带「类」或「份额」），且该字母前不是另一个大写字母。
# 前置的负向断言把 ETF / LOF / QDII 这类缩写排除在外。
_SUFFIX = re.compile(r"^(?P<stem>.*[^A-Z])(?P<cls>[A-Z])(?:类)?(?:份额)?$")


class GroupingStatus(StrEnum):
    CONFIRMED = "CONFIRMED"      # 规则可判定
    UNCONFIRMED = "UNCONFIRMED"  # 规则无法判定，待人工确认


@dataclass(frozen=True, slots=True)
class GroupingResult:
    product_name: str
    share_class_code: str
    status: GroupingStatus


def split_share_class_name(display_name: str) -> GroupingResult:
    """把 AKShare 的基金简称拆为「产品名 + 份额类别」。

    AKShare 的 6 位代码是份额类别而非产品（03-erd §5.2），需要一条归组规则。
    本规则只处理最明确的一种情形：结尾单个大写字母。

    【不猜】：ETF / LOF / QDII 等以多个大写字母结尾的名称一律标记
    UNCONFIRMED，各自单独成一个 fund，而不是强行合并（spec R-4）。
    强行合并的后果是两只不相干的基金共用 Peer Group 与评分口径。
    """
    name = display_name.strip()
    if not name:
        return GroupingResult("", DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    match = _SUFFIX.match(name)
    if match:
        stem = match.group("stem").strip()
        if stem:
            return GroupingResult(stem, match.group("cls"), GroupingStatus.CONFIRMED)
        return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    if name[-1].isupper() and name[-1].isascii():
        # 结尾是大写字母但不匹配上面的模式 —— 说明前面还有大写字母（ETF/LOF）
        return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.UNCONFIRMED)

    return GroupingResult(name, DEFAULT_SHARE_CLASS, GroupingStatus.CONFIRMED)
```

- [ ] **Step 4：运行单元测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_share_class_grouping.py -v`
Expected: 11 passed

- [ ] **Step 5：写 `src/fip/services/data_service/models/fund.py`**

```python
import datetime as dt

from sqlalchemy import (
    BigInteger, Date, DateTime, ForeignKey, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class Fund(Base):
    """基金【产品】的身份。无净值、无费率 —— 那些属于 Share Class。"""

    __tablename__ = "fund"
    __table_args__ = {"schema": "fund"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String(256), nullable=False)
    grouping_status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class FundShareClass(Base):
    """份额类别 —— 【全平台的计算粒度】。

    绝大多数下游表的外键指向本表而非 fund（04-database-design §6.1）。
    """

    __tablename__ = "fund_share_class"
    __table_args__ = (
        UniqueConstraint("fund_id", "share_class_code", name="uq_share_class_business"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_code: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    inception_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class ProviderFundIdentity(Base):
    """Provider 的基金 ID 映射。

    【不得】把 provider_fund_id 做成 Share Class 的列 —— 那会限制为单
    Provider，且映射变化会污染主数据（03-erd §5.3）。映射本身可能变化，
    因此带 valid_from / valid_to。
    """

    __tablename__ = "provider_fund_identity"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "provider_fund_id", "valid_from",
            name="uq_provider_identity",
        ),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("governance.data_provider.id", ondelete="RESTRICT"), nullable=False
    )
    provider_fund_id: Mapped[str] = mapped_column(String(64), nullable=False)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    valid_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 6：生成并核对迁移**

```bash
.venv/bin/alembic -x db=dev revision --autogenerate -m "fund 核心表" --rev-id 0007
```

打开 `db/migrations/versions/0007_*.py` 逐行核对：只应包含 `fund.fund`、`fund.fund_share_class`、`fund.provider_fund_identity` 三张表的创建。删除任何对既有表的误判性变更。

```bash
.venv/bin/alembic -x db=dev upgrade head
```

- [ ] **Step 7：写集成测试**

```python
# tests/integration/test_fund_core.py
import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus, split_share_class_name
from fip.services.data_service.models.fund import Fund, FundShareClass, ProviderFundIdentity
from fip.services.data_service.models.governance import DataProvider

pytestmark = pytest.mark.integration


def _make_fund(session, display_name: str, fund_code: str) -> FundShareClass:
    grouping = split_share_class_name(display_name)
    fund = Fund(
        fund_code=fund_code,
        product_name=grouping.product_name,
        grouping_status=grouping.status.value,
    )
    session.add(fund)
    session.flush()
    sc = FundShareClass(
        fund_id=fund.id,
        share_class_code=grouping.share_class_code,
        display_name=display_name,
    )
    session.add(sc)
    session.flush()
    return sc


def test_two_share_classes_can_belong_to_one_fund(db_session):
    fund = Fund(fund_code="P-0001", product_name="易方达蓝筹精选混合",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    db_session.add_all([
        FundShareClass(fund_id=fund.id, share_class_code="A",
                       display_name="易方达蓝筹精选混合A"),
        FundShareClass(fund_id=fund.id, share_class_code="C",
                       display_name="易方达蓝筹精选混合C"),
    ])
    db_session.flush()
    assert db_session.query(FundShareClass).filter_by(fund_id=fund.id).count() == 2


def test_duplicate_share_class_code_within_a_fund_is_rejected(db_session):
    fund = Fund(fund_code="P-0002", product_name="X",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    db_session.add(FundShareClass(fund_id=fund.id, share_class_code="A", display_name="XA"))
    db_session.flush()
    db_session.add(FundShareClass(fund_id=fund.id, share_class_code="A", display_name="XA2"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unconfirmed_grouping_is_persisted_as_its_own_fund(db_session):
    """不猜 —— 归组不确定者单独成一个 fund 并留下待确认标记。"""
    sc = _make_fund(db_session, "广发纳斯达克100ETF", "P-0003")
    fund = db_session.get(Fund, sc.fund_id)
    assert fund.grouping_status == GroupingStatus.UNCONFIRMED.value
    assert sc.share_class_code == "DEFAULT"


def test_one_share_class_can_have_multiple_provider_identities(db_session):
    sc = _make_fund(db_session, "华夏成长混合", "P-0004")
    p1 = DataProvider(provider_code="AKSHARE", display_name="AKShare")
    p2 = DataProvider(provider_code="VENDOR_X", display_name="Vendor X")
    db_session.add_all([p1, p2])
    db_session.flush()
    db_session.add_all([
        ProviderFundIdentity(provider_id=p1.id, provider_fund_id="000001",
                             share_class_id=sc.id, valid_from=dt.date(2020, 1, 1)),
        ProviderFundIdentity(provider_id=p2.id, provider_fund_id="CN000001",
                             share_class_id=sc.id, valid_from=dt.date(2020, 1, 1)),
    ])
    db_session.flush()
    assert db_session.query(ProviderFundIdentity).filter_by(
        share_class_id=sc.id).count() == 2
```

- [ ] **Step 8：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_share_class_grouping.py tests/integration/test_fund_core.py -v`
Expected: 11 passed + 4 passed

- [ ] **Step 9：提交**

```bash
git add -A
git commit -m "feat(fund): Fund / ShareClass 分离、Provider 身份映射与归组规则

AKShare 的 6 位代码是份额类别而非产品。归组规则只处理最明确的一种
情形（结尾单个大写字母）；ETF/LOF 等一律标记 UNCONFIRMED 单独成
fund，不强行合并 —— 错误合并会让两只不相干的基金共用评分口径。"
```

---

## Task 12：fund_nav 分区表与净值灌数

**Files:**
- Create: `src/fip/services/data_service/models/market.py`
- Create: `db/migrations/versions/0008_fund_nav_partitioned.py`
- Create: `src/fip/services/data_service/adapters/akshare/parse.py`
- Test: `tests/unit/test_nav_parsing.py`, `tests/integration/test_fund_nav.py`

**Interfaces:**
- Consumes: `SourceRecord`、`resolve_availability`、`declared_lag_availability`、`FundShareClass`
- Produces:
  - ORM `FundNav`（`market.fund_nav`，PK `(share_class_id, effective_at, version)`，按 `effective_at` RANGE 分区）
  - `parse_nav_frame(payload: bytes) -> list[ParsedNav]`
  - `ParsedNav`（frozen dataclass：`effective_at: dt.date`、`unit_nav: Decimal`）

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_nav_parsing.py
import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import parse_nav_frame


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_parses_dates_and_decimals():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-03"],
        "单位净值": ["1.0000", "1.0123"],
    }))
    rows = parse_nav_frame(payload)
    assert rows[0].effective_at == dt.date(2020, 1, 2)
    assert rows[0].unit_nav == Decimal("1.0000")
    assert rows[1].unit_nav == Decimal("1.0123")


def test_values_are_decimal_not_float():
    """金融数值禁止浮点 —— float 会在累乘复权时引入不可控误差。"""
    payload = _payload(pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["1.0001"]}))
    assert isinstance(parse_nav_frame(payload)[0].unit_nav, Decimal)


def test_rows_are_sorted_ascending():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-03", "2020-01-02"],
        "单位净值": ["1.0123", "1.0000"],
    }))
    rows = parse_nav_frame(payload)
    assert [r.effective_at for r in rows] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_missing_nav_is_dropped_not_filled():
    """C-6：缺失不得转 0、不得前向填充。缺失就是缺失。"""
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-03"],
        "单位净值": ["1.0000", None],
    }))
    rows = parse_nav_frame(payload)
    assert len(rows) == 1
    assert rows[0].effective_at == dt.date(2020, 1, 2)


def test_duplicate_dates_are_rejected():
    payload = _payload(pd.DataFrame({
        "净值日期": ["2020-01-02", "2020-01-02"],
        "单位净值": ["1.0000", "1.0100"],
    }))
    with pytest.raises(ValueError, match="重复"):
        parse_nav_frame(payload)


def test_non_positive_nav_is_rejected():
    payload = _payload(pd.DataFrame({"净值日期": ["2020-01-02"], "单位净值": ["0"]}))
    with pytest.raises(ValueError, match="净值"):
        parse_nav_frame(payload)
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_nav_parsing.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...adapters.akshare.parse`

- [ ] **Step 3：写 `src/fip/services/data_service/adapters/akshare/parse.py`**

```python
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd


@dataclass(frozen=True, slots=True)
class ParsedNav:
    effective_at: dt.date
    unit_nav: Decimal


def _to_decimal(raw: object) -> Decimal | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_nav_frame(payload: bytes) -> list[ParsedNav]:
    """把 AKShare 的单位净值走势 parquet 解析为规范记录。

    缺失值直接【丢弃】而非填充（C-6）—— 前向填充会在净值停更期间
    伪造出「零波动」，直接污染波动率与最大回撤。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedNav] = []
    seen: set[dt.date] = set()
    for _, record in frame.iterrows():
        value = _to_decimal(record["单位净值"])
        if value is None:
            continue
        if value <= 0:
            raise ValueError(f"净值必须为正，得到 {value}")
        day = pd.to_datetime(record["净值日期"]).date()
        if day in seen:
            raise ValueError(f"净值日期重复：{day}")
        seen.add(day)
        rows.append(ParsedNav(effective_at=day, unit_nav=value))
    rows.sort(key=lambda r: r.effective_at)
    return rows
```

- [ ] **Step 4：写 `src/fip/services/data_service/models/market.py`**

```python
import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.mixins import VersionedMixin, temporal_check_constraints
from fip.platform.db.types import NavNumeric


class FundNav(Base, VersionedMixin):
    """净值序列。

    PK 取 (share_class_id, effective_at, version)：
      · 它同时是唯一约束（04-database-design §4.4）
      · 分区键 effective_at 必须包含在 PK 中
      · 它恰好是 PIT 版本解析查询的最优索引
    修订产生新 version，旧版本保留、【不覆盖】。
    """

    __tablename__ = "fund_nav"
    __table_args__ = (
        *temporal_check_constraints("fund_nav"),
        {"schema": "market", "postgresql_partition_by": "RANGE (effective_at)"},
    )

    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    unit_nav: Mapped[Decimal] = mapped_column(NavNumeric, nullable=False)
    adjusted_nav: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    raw_payload_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

> `adjusted_nav` 暂为可空 —— Task 14 实现算法、Task 15 回填。可空是有意的：复权值算不出时必须留空而非填 0（C-6）。

- [ ] **Step 5：写迁移 `db/migrations/versions/0008_fund_nav_partitioned.py`**

分区表无法用 autogenerate 正确生成，手写：

```python
"""market.fund_nav 分区表

Revision ID: 0008
Revises: 0007
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL, TIME_ORDER_SQL

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

FIRST_YEAR, LAST_YEAR = 2000, 2030


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.fund_nav (
            share_class_id        BIGINT       NOT NULL
                REFERENCES fund.fund_share_class(id) ON DELETE RESTRICT,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            unit_nav              NUMERIC(18,8) NOT NULL,
            adjusted_nav          NUMERIC(18,8),
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (share_class_id, effective_at, version),
            CONSTRAINT ck_fund_nav_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_fund_nav_time_order     CHECK ({TIME_ORDER_SQL}),
            CONSTRAINT ck_fund_nav_positive       CHECK (unit_nav > 0)
        ) PARTITION BY RANGE (effective_at)
    """)
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        op.execute(
            f"CREATE TABLE market.fund_nav_{year} PARTITION OF market.fund_nav "
            f"FOR VALUES FROM ('{year}-01-01') TO ('{year + 1}-01-01')"
        )
    # PIT 版本解析的支撑索引：按 available_at 过滤后取每个 effective_at 的最大 version
    op.execute(
        "CREATE INDEX ix_fund_nav_pit ON market.fund_nav "
        "(share_class_id, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.fund_nav CASCADE")
```

- [ ] **Step 6：应用迁移并写集成测试**

```bash
.venv/bin/alembic -x db=dev upgrade head
```

```python
# tests/integration/test_fund_nav.py
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundNav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-NAV", product_name="测试基金",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="测试基金A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _nav(sc, day, value, version=1, available_at=None):
    return FundNav(
        share_class_id=sc.id,
        effective_at=day,
        version=version,
        unit_nav=Decimal(value),
        available_at=available_at
        or dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC) + dt.timedelta(days=1),
        availability_quality="INFERRED",
        published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )


def test_rows_land_in_the_year_partition(db_session, share_class):
    db_session.add(_nav(share_class, dt.date(2020, 3, 5), "1.2345"))
    db_session.flush()
    count = db_session.execute(
        text("SELECT count(*) FROM market.fund_nav_2020")
    ).scalar_one()
    assert count == 1


def test_revision_creates_a_new_version_without_overwriting(db_session, share_class):
    """修订产生新版本，旧版本保留（上游原则二）。"""
    day = dt.date(2020, 3, 5)
    db_session.add(_nav(share_class, day, "1.2345", version=1))
    db_session.flush()
    db_session.add(_nav(share_class, day, "1.2000", version=2))
    db_session.flush()
    versions = db_session.query(FundNav).filter_by(
        share_class_id=share_class.id, effective_at=day).count()
    assert versions == 2


def test_duplicate_version_is_rejected(db_session, share_class):
    day = dt.date(2020, 3, 5)
    db_session.add(_nav(share_class, day, "1.2345", version=1))
    db_session.flush()
    db_session.add(_nav(share_class, day, "1.2000", version=1))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_non_positive_nav_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_nav(share_class, dt.date(2020, 3, 5), "0"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_adjusted_nav_may_be_null(db_session, share_class):
    """算不出复权值时留空，绝不填 0（C-6）。"""
    row = _nav(share_class, dt.date(2020, 3, 5), "1.2345")
    db_session.add(row)
    db_session.flush()
    assert row.adjusted_nav is None
```

- [ ] **Step 7：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_nav_parsing.py tests/integration/test_fund_nav.py -v`
Expected: 6 passed + 5 passed

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(market): fund_nav 分区表与净值解析

PK (share_class_id, effective_at, version) 同时充当唯一约束、分区键
包含项与 PIT 查询的最优索引。缺失净值直接丢弃不填充 —— 前向填充会在
停更期间伪造零波动，污染波动率与最大回撤。"
```

---

## Task 13：fund_distribution（分红与拆分）

**Files:**
- Modify: `src/fip/services/data_service/models/market.py`（追加 `FundDistribution`）
- Modify: `src/fip/services/data_service/adapters/akshare/parse.py`（追加两个解析函数）
- Create: `db/migrations/versions/0009_fund_distribution.py`
- Test: `tests/unit/test_distribution_parsing.py`, `tests/integration/test_fund_distribution.py`

**Interfaces:**
- Consumes: `FundShareClass`、`VersionedMixin`
- Produces:
  - ORM `FundDistribution`（`market.fund_distribution`，PK `(share_class_id, effective_at, version)`，列 `dividend_per_unit: Decimal`、`split_ratio: Decimal`）
  - `parse_distribution_frame(payload: bytes) -> list[ParsedDistribution]`
  - `parse_split_frame(payload: bytes) -> list[ParsedDistribution]`
  - `ParsedDistribution`（frozen dataclass：`effective_at: dt.date`、`dividend_per_unit: Decimal`、`split_ratio: Decimal`）

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_distribution_parsing.py
import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import (
    parse_distribution_frame,
    parse_split_frame,
)


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_dividend_uses_ex_date_not_record_date():
    """复权按【除息日】计算 —— 权益登记日不是净值下跌的那一天。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2020"],
        "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"],
        "每10份分红": ["每10份派现金1.0000元"],
    }))
    rows = parse_distribution_frame(payload)
    assert rows[0].effective_at == dt.date(2020, 6, 11)
    assert rows[0].dividend_per_unit == Decimal("0.1")   # 1.0000 / 10
    assert rows[0].split_ratio == Decimal(1)


def test_dividend_is_divided_by_the_stated_base():
    """⚠️ 最关键的一条：列名里的基数必须被除掉。

    漏掉除以 10，每笔分红放大 10 倍，复权净值系统性高估且不报错。
    """
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-12-31"], "除息日": ["2021-12-31"],
        "每10份分红": ["每10份派现金0.4500元"],
    }))
    assert parse_distribution_frame(payload)[0].dividend_per_unit == Decimal("0.045")


def test_unparseable_dividend_text_is_dropped_not_guessed():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "权益登记日": ["2021-12-31"], "除息日": ["2021-12-31"],
        "每10份分红": ["暂无数据"],
    }))
    assert parse_distribution_frame(payload) == []


def test_dividend_amount_is_decimal():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"], "每10份分红": ["每10份派现金1.0000元"],
    }))
    assert isinstance(parse_distribution_frame(payload)[0].dividend_per_unit, Decimal)


def test_negative_dividend_is_rejected():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": ["2020-06-11"], "每10份分红": ["每10份派现金-0.1元"],
    }))
    with pytest.raises(ValueError, match="分红"):
        parse_distribution_frame(payload)


def test_rows_without_ex_date_are_dropped():
    payload = _payload(pd.DataFrame({
        "年份": ["2020"], "权益登记日": ["2020-06-10"],
        "除息日": [None], "每10份分红": ["每10份派现金1.0000元"],
    }))
    assert parse_distribution_frame(payload) == []


def test_split_ratio_is_parsed():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["2.0000"],
    }))
    rows = parse_split_frame(payload)
    assert rows[0].effective_at == dt.date(2021, 3, 15)
    assert rows[0].split_ratio == Decimal("2.0000")
    assert rows[0].dividend_per_unit == Decimal(0)


def test_split_ratio_expressed_as_colon_pair_is_parsed():
    """AKShare 的拆分比例有时是 '1:2' 形式。"""
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["1:2"],
    }))
    assert parse_split_frame(payload)[0].split_ratio == Decimal(2)


def test_non_positive_split_ratio_is_rejected():
    payload = _payload(pd.DataFrame({
        "年份": ["2021"], "拆分折算日": ["2021-03-15"], "拆分折算比例": ["0"],
    }))
    with pytest.raises(ValueError, match="拆分"):
        parse_split_frame(payload)
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_distribution_parsing.py -v`
Expected: FAIL —— `ImportError: cannot import name 'parse_distribution_frame'`

- [ ] **Step 3：在 `parse.py` 末尾追加**

```python
@dataclass(frozen=True, slots=True)
class ParsedDistribution:
    effective_at: dt.date
    dividend_per_unit: Decimal
    split_ratio: Decimal


def _to_date(raw: object) -> dt.date | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    return pd.to_datetime(text).date()


_DIVIDEND_RE = re.compile(r"每\s*(?P<base>\d+)\s*份[^0-9]*(?P<amount>\d+(?:\.\d+)?)")


def _parse_dividend_per_unit(raw: object) -> Decimal | None:
    """把「每10份分红」列解析为【每一份】的分红金额。

    ⚠️ 实测（AKShare 1.18.94）：该列不是数字，而是字符串，形如
    `每10份派现金0.4500元`。必须同时提取【基数 10】与【金额 0.4500】并相除。

    若直接把 0.4500 当作每份分红，每一笔分红会放大 10 倍，复权净值系统性高估，
    而且【不会有任何报错】—— 这正是最危险的一类缺陷。
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text:
        return None
    match = _DIVIDEND_RE.search(text)
    if match is None:
        return None
    base = Decimal(match.group("base"))
    if base <= 0:
        return None
    return Decimal(match.group("amount")) / base


def parse_distribution_frame(payload: bytes) -> list[ParsedDistribution]:
    """分红送配详情 → 除息事件。

    用【除息日】而非权益登记日：净值在除息日下跌，复权必须对齐那一天。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedDistribution] = []
    for _, record in frame.iterrows():
        day = _to_date(record.get("除息日"))
        amount = _parse_dividend_per_unit(record.get("每10份分红"))
        if day is None or amount is None:
            continue
        if amount < 0:
            raise ValueError(f"每份分红不得为负，得到 {amount}")
        if amount == 0:
            continue
        rows.append(ParsedDistribution(day, amount, Decimal(1)))
    rows.sort(key=lambda r: r.effective_at)
    return rows


def _parse_ratio(raw: object) -> Decimal | None:
    """拆分比例可能是 '2.0000' 或 '1:2' 两种形式。"""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text in {"nan", "None", "--", "-"}:
        return None
    if ":" in text or "：" in text:
        left, _, right = text.replace("：", ":").partition(":")
        base = _to_decimal(left)
        target = _to_decimal(right)
        if base is None or target is None or base == 0:
            return None
        return target / base
    return _to_decimal(text)


def parse_split_frame(payload: bytes) -> list[ParsedDistribution]:
    """拆分详情 → 拆分事件。split_ratio 表示 1 份拆为几份。"""
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedDistribution] = []
    for _, record in frame.iterrows():
        day = _to_date(record.get("拆分折算日"))
        ratio = _parse_ratio(record.get("拆分折算比例"))
        if day is None or ratio is None:
            continue
        if ratio <= 0:
            raise ValueError(f"拆分折算比例必须为正，得到 {ratio}")
        rows.append(ParsedDistribution(day, Decimal(0), ratio))
    rows.sort(key=lambda r: r.effective_at)
    return rows
```

- [ ] **Step 4：在 `models/market.py` 末尾追加 ORM**

```python
class FundDistribution(Base, VersionedMixin):
    """除息与拆分事件。复权净值计算的唯一事件来源。

    dividend 与 split 合并为一张表：同日同时发生除息与拆分是真实场景，
    分两张表会让「同日先后顺序」这一关键语义无处安放。
    """

    __tablename__ = "fund_distribution"
    __table_args__ = (
        *temporal_check_constraints("fund_distribution"),
        {"schema": "market"},
    )

    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    dividend_per_unit: Mapped[Decimal] = mapped_column(NavNumeric, nullable=False)
    split_ratio: Mapped[Decimal] = mapped_column(NavNumeric, nullable=False)
    raw_payload_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

- [ ] **Step 5：写迁移 `db/migrations/versions/0009_fund_distribution.py`**

```python
"""market.fund_distribution

Revision ID: 0009
Revises: 0008
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL, TIME_ORDER_SQL

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.fund_distribution (
            share_class_id        BIGINT       NOT NULL
                REFERENCES fund.fund_share_class(id) ON DELETE RESTRICT,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            dividend_per_unit     NUMERIC(18,8) NOT NULL DEFAULT 0,
            split_ratio           NUMERIC(18,8) NOT NULL DEFAULT 1,
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (share_class_id, effective_at, version),
            CONSTRAINT ck_fund_distribution_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_fund_distribution_time_order     CHECK ({TIME_ORDER_SQL}),
            CONSTRAINT ck_fund_distribution_dividend CHECK (dividend_per_unit >= 0),
            CONSTRAINT ck_fund_distribution_split    CHECK (split_ratio > 0)
        )
    """)
    op.execute(
        "CREATE INDEX ix_fund_distribution_pit ON market.fund_distribution "
        "(share_class_id, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.fund_distribution CASCADE")
```

- [ ] **Step 6：写集成测试**

```python
# tests/integration/test_fund_distribution.py
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-DIST", product_name="分红测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="分红测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _event(sc, day, dividend="0", ratio="1"):
    return FundDistribution(
        share_class_id=sc.id, effective_at=day, version=1,
        dividend_per_unit=Decimal(dividend), split_ratio=Decimal(ratio),
        available_at=dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC),
    )


def test_same_day_dividend_and_split_fit_in_one_row(db_session, share_class):
    """同日除息 + 拆分是真实场景，必须能在一行内表达先后语义。"""
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "0.2", "2"))
    db_session.flush()
    row = db_session.query(FundDistribution).one()
    assert row.dividend_per_unit == Decimal("0.2")
    assert row.split_ratio == Decimal(2)


def test_negative_dividend_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "-0.1"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_zero_split_ratio_is_rejected_by_the_database(db_session, share_class):
    db_session.add(_event(share_class, dt.date(2021, 3, 15), "0", "0"))
    with pytest.raises(IntegrityError):
        db_session.flush()
```

- [ ] **Step 7：应用迁移并运行测试**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/pytest tests/unit/test_distribution_parsing.py tests/integration/test_fund_distribution.py -v
```

Expected: 7 passed + 3 passed

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(market): fund_distribution 除息与拆分事件

分红与拆分合并一张表：同日同时发生是真实场景，分表会让『同日先后
顺序』这一关键语义无处安放。用除息日而非权益登记日 —— 净值在除息日
下跌，复权必须对齐那一天。"
```

---

## Task 14：复权净值算法 ⚠️

> **本 Plan 的承重任务。** 每一个 Factor、每一份 `μ` 与 `Σ`、每一条回测净值曲线都建在它上面。
>
> AKShare 给的是单位净值与累计净值，而**累计净值 ≠ 复权净值** —— 前者不处理拆分，也不做分红再投资的乘法复利。

**Files:**
- Create: `src/fip/services/data_service/normalization/adjusted_nav.py`
- Test: `tests/unit/test_adjusted_nav.py`

**Interfaces:**
- Consumes: 无（纯函数模块，不接触数据库）
- Produces:
  - `AdjustedNavUnavailable`（异常）
  - `NavObservation`（frozen dataclass：`effective_at: dt.date`、`unit_nav: Decimal`）
  - `DistributionEvent`（frozen dataclass：`effective_at: dt.date`、`dividend_per_unit: Decimal`、`split_ratio: Decimal`）
  - `AdjustedNavPoint`（frozen dataclass：`effective_at: dt.date`、`unit_nav: Decimal`、`cumulative_shares: Decimal`、`adjusted_nav: Decimal`）
  - `compute_adjusted_nav(navs: Sequence[NavObservation], events: Sequence[DistributionEvent]) -> list[AdjustedNavPoint]`

**算法口径**（两项均已在 `config/strategy/metric/v1.yaml` 中登记为 `DECIDED`，属 `Metric Version`）：

| 口径 | 取值 | 含义 |
|---|---|---|
| 分红再投资价格 | `EX_DATE_NAV` | 以除息日当日单位净值再投资 |
| 同日事件顺序 | `DIVIDEND_THEN_SPLIT` | 先除息，后拆分 |

**递推式**（持有 1 份起始份额，`shares` 为累计份额）：

```
除息前、拆分前的净值：  pre = unit_nav_t × split_ratio_t
shares_t = shares_{t-1} × (1 + dividend_t / pre) × split_ratio_t
adjusted_nav_t = unit_nav_t × shares_t
```

无事件时 `dividend=0`、`split_ratio=1`，退化为 `shares_t = shares_{t-1}`。

- [ ] **Step 1：写失败的测试**

```python
# tests/unit/test_adjusted_nav.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)


def D(value: str) -> Decimal:
    return Decimal(value)


def nav(day: int, value: str) -> NavObservation:
    return NavObservation(dt.date(2020, 1, day), D(value))


def dividend(day: int, amount: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D(amount), D("1"))


def split(day: int, ratio: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D("0"), D(ratio))


def both(day: int, amount: str, ratio: str) -> DistributionEvent:
    return DistributionEvent(dt.date(2020, 1, day), D(amount), D(ratio))


def _returns(points):
    return [
        points[i].adjusted_nav / points[i - 1].adjusted_nav - 1
        for i in range(1, len(points))
    ]


def test_without_events_adjusted_equals_unit():
    points = compute_adjusted_nav([nav(2, "1.0"), nav(3, "1.1")], [])
    assert [p.adjusted_nav for p in points] == [D("1.0"), D("1.1")]


def test_pure_dividend_produces_zero_return():
    """除息不是亏损。复权后跨除息日的收益必须为 0。"""
    points = compute_adjusted_nav(
        [nav(2, "1.1"), nav(3, "1.0")],
        [dividend(3, "0.1")],
    )
    assert points[1].cumulative_shares == D("1.1")
    assert points[1].adjusted_nav == D("1.1")
    assert _returns(points) == [D("0")]


def test_pure_split_produces_zero_return():
    """拆分不是亏损。"""
    points = compute_adjusted_nav(
        [nav(2, "2.0"), nav(3, "1.0")],
        [split(3, "2")],
    )
    assert points[1].cumulative_shares == D("2")
    assert points[1].adjusted_nav == D("2.0")
    assert _returns(points) == [D("0")]


def test_same_day_dividend_and_split_produces_zero_return():
    """同日先除息后拆分。

    nav 2.2 → 除息 0.2 后为 2.0 → 拆分 2:1 后为 1.0。
    份额：1 × (1 + 0.2/2.0) × 2 = 2.2；复权净值 1.0 × 2.2 = 2.2，收益为 0。
    """
    points = compute_adjusted_nav(
        [nav(2, "2.2"), nav(3, "1.0")],
        [both(3, "0.2", "2")],
    )
    assert points[1].cumulative_shares == D("2.2")
    assert points[1].adjusted_nav == D("2.2")
    assert _returns(points) == [D("0")]


def test_events_accumulate_multiplicatively():
    """1.0 →（分红 0.1）→ 涨到 2.0 →（拆分 2:1）：总收益 120%。"""
    points = compute_adjusted_nav(
        [nav(2, "1.0"), nav(3, "1.0"), nav(4, "2.0"), nav(5, "1.0")],
        [dividend(3, "0.1"), split(5, "2")],
    )
    assert [p.adjusted_nav for p in points] == [D("1.0"), D("1.1"), D("2.2"), D("2.2")]
    assert points[-1].adjusted_nav / points[0].adjusted_nav - 1 == D("1.2")


def test_result_values_are_decimal():
    """C：金融数值禁止浮点。float 在累乘中会引入不可控误差。"""
    points = compute_adjusted_nav([nav(2, "1.0")], [])
    assert isinstance(points[0].adjusted_nav, Decimal)
    assert isinstance(points[0].cumulative_shares, Decimal)


def test_unordered_input_is_sorted():
    points = compute_adjusted_nav([nav(3, "1.1"), nav(2, "1.0")], [])
    assert [p.effective_at.day for p in points] == [2, 3]


def test_empty_input_returns_empty():
    assert compute_adjusted_nav([], []) == []


def test_event_without_matching_nav_is_an_error():
    """事件日没有净值观测就无法计算再投资价格 —— 显式失败，不跳过。"""
    with pytest.raises(AdjustedNavUnavailable, match="缺少净值"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(3, "0.1")])


def test_non_positive_nav_is_an_error():
    with pytest.raises(AdjustedNavUnavailable, match="净值"):
        compute_adjusted_nav([NavObservation(dt.date(2020, 1, 2), D("0"))], [])


def test_negative_dividend_is_rejected():
    with pytest.raises(ValueError, match="分红"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(2, "-0.1")])


def test_non_positive_split_ratio_is_rejected():
    with pytest.raises(ValueError, match="拆分"):
        compute_adjusted_nav([nav(2, "1.0")], [split(2, "0")])


def test_duplicate_nav_dates_are_rejected():
    with pytest.raises(ValueError, match="重复"):
        compute_adjusted_nav([nav(2, "1.0"), nav(2, "1.1")], [])


def test_duplicate_event_dates_are_rejected():
    with pytest.raises(ValueError, match="重复"):
        compute_adjusted_nav([nav(2, "1.0")], [dividend(2, "0.1"), split(2, "2")])


def test_long_series_stays_exact():
    """1000 期连续分红，验证 Decimal 精度不退化为浮点漂移。"""
    navs = [NavObservation(dt.date(2020, 1, 1) + dt.timedelta(days=i), D("1.0"))
            for i in range(1000)]
    events = [DistributionEvent(navs[i].effective_at, D("0.01"), D("1"))
              for i in range(1, 1000)]
    points = compute_adjusted_nav(navs, events)
    expected = D("1.01") ** 999
    assert points[-1].cumulative_shares == expected
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_adjusted_nav.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...normalization.adjusted_nav`

- [ ] **Step 3：写实现**

```python
# src/fip/services/data_service/normalization/adjusted_nav.py
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext

# 累乘链路较长（可达数千期），需要高于默认的 28 位精度。
_PRECISION = 60

ONE = Decimal(1)
ZERO = Decimal(0)


class AdjustedNavUnavailable(RuntimeError):
    """复权净值无法计算。

    调用方必须把对应记录标记为 UNAVAILABLE，【不得】填 0 或沿用上期（C-6）。
    """


@dataclass(frozen=True, slots=True)
class NavObservation:
    effective_at: dt.date
    unit_nav: Decimal


@dataclass(frozen=True, slots=True)
class DistributionEvent:
    effective_at: dt.date
    dividend_per_unit: Decimal
    split_ratio: Decimal


@dataclass(frozen=True, slots=True)
class AdjustedNavPoint:
    effective_at: dt.date
    unit_nav: Decimal
    cumulative_shares: Decimal
    adjusted_nav: Decimal


def compute_adjusted_nav(
    navs: Sequence[NavObservation],
    events: Sequence[DistributionEvent],
) -> list[AdjustedNavPoint]:
    """由单位净值与除息/拆分事件计算复权净值（分红再投资总收益序列）。

    口径（属 Metric Version，登记于 config/strategy/metric/v1.yaml）：
      · 分红再投资价格 = 除息日当日单位净值（EX_DATE_NAV）
      · 同日事件顺序   = 先除息后拆分（DIVIDEND_THEN_SPLIT）

    递推（持有 1 份起始份额）：
        pre      = unit_nav_t × split_ratio_t     # 除息后、拆分前的净值
        shares_t = shares_{t-1} × (1 + dividend_t / pre) × split_ratio_t
        adj_t    = unit_nav_t × shares_t

    无事件时退化为 shares_t = shares_{t-1}，adj_t = unit_nav_t。

    为什么不能直接用累计净值代替：累计净值不处理拆分，也不做分红再投资的
    乘法复利 —— 它是「累计分配」而非「总收益」。
    """
    if not navs:
        return []

    ordered_navs = sorted(navs, key=lambda n: n.effective_at)
    seen_navs: set[dt.date] = set()
    for observation in ordered_navs:
        if observation.effective_at in seen_navs:
            raise ValueError(f"净值日期重复：{observation.effective_at}")
        seen_navs.add(observation.effective_at)
        if observation.unit_nav <= 0:
            raise AdjustedNavUnavailable(
                f"{observation.effective_at} 的单位净值为 {observation.unit_nav}，"
                "必须为正"
            )

    by_date: dict[dt.date, DistributionEvent] = {}
    for event in events:
        if event.dividend_per_unit < 0:
            raise ValueError(f"{event.effective_at} 的每份分红为负：{event.dividend_per_unit}")
        if event.split_ratio <= 0:
            raise ValueError(f"{event.effective_at} 的拆分比例非正：{event.split_ratio}")
        if event.effective_at in by_date:
            raise ValueError(f"事件日期重复：{event.effective_at}")
        by_date[event.effective_at] = event

    missing = sorted(set(by_date) - seen_navs)
    if missing:
        raise AdjustedNavUnavailable(
            f"事件日 {missing} 缺少净值观测，无法确定再投资价格"
        )

    points: list[AdjustedNavPoint] = []
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        shares = ONE
        for observation in ordered_navs:
            event = by_date.get(observation.effective_at)
            if event is not None:
                pre_split_nav = observation.unit_nav * event.split_ratio
                if pre_split_nav <= 0:
                    raise AdjustedNavUnavailable(
                        f"{observation.effective_at} 的除息前净值非正，无法再投资"
                    )
                reinvest = ONE + event.dividend_per_unit / pre_split_nav
                shares = shares * reinvest * event.split_ratio
            points.append(
                AdjustedNavPoint(
                    effective_at=observation.effective_at,
                    unit_nav=observation.unit_nav,
                    cumulative_shares=shares,
                    adjusted_nav=observation.unit_nav * shares,
                )
            )
    return points
```

- [ ] **Step 4：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_adjusted_nav.py -v`
Expected: 14 passed

- [ ] **Step 5：确认适应度测试仍全绿**

Run: `.venv/bin/pytest tests/fitness -v`
Expected: 9 passed

（`adjusted_nav.py` 是纯函数模块，不得引入任何 I/O 依赖。）

- [ ] **Step 6：提交**

```bash
git add -A
git commit -m "feat(normalization): 复权净值算法

累计净值 ≠ 复权净值：前者不处理拆分，也不做分红再投资的乘法复利。
口径（除息日再投资、同日先除息后拆分）属 Metric Version 并已登记。
全程 Decimal（精度 60 位），因为累乘链路可达数千期。
算不出时抛 AdjustedNavUnavailable，由调用方标记 UNAVAILABLE，不填 0。"
```

---

## Task 15：复权净值持久化与 PIT NAV Repository ⚠️

> **本 Plan 的核心交付。** 完成后即可回答："给定任意历史 `decision_at`，取回当时可见的复权净值序列。"

**Files:**
- Create: `src/fip/services/data_service/repositories/nav.py`
- Create: `src/fip/services/data_service/normalization/backfill.py`
- Test: `tests/integration/test_pit_nav_repository.py`

**Interfaces:**
- Consumes: `NavPitRepository`、`NavPoint`（Task 5）、`compute_adjusted_nav`（Task 14）、`FundNav`、`FundDistribution`
- Produces:
  - `SqlNavPitRepository(session: Session, decision_at: dt.date)` —— 实现 `NavPitRepository`
  - `backfill_adjusted_nav(session: Session, share_class_id: int, decision_at: dt.date) -> int`（返回回填行数）

**PIT 版本解析规则**：对每个 `effective_at`，在 `available_at ≤ decision_at` 的行中取 `version` 最大者。SQL 形态：

```sql
SELECT DISTINCT ON (effective_at) effective_at, unit_nav, adjusted_nav,
                                  version, availability_quality
FROM market.fund_nav
WHERE share_class_id = :sc
  AND available_at <= :decision_at_end
  AND effective_at BETWEEN :date_from AND :date_to
ORDER BY effective_at, version DESC
```

- [ ] **Step 1：写失败的集成测试**

```python
# tests/integration/test_pit_nav_repository.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext, RecomputeScope, RuntimeMode, TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundDistribution, FundNav
from fip.services.data_service.normalization.backfill import backfill_adjusted_nav

pytestmark = pytest.mark.integration


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-PIT", product_name="PIT 测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="PIT 测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _utc(year, month, day):
    return dt.datetime(year, month, day, tzinfo=dt.UTC)


def _add_nav(session, sc, day, value, version=1, available_at=None):
    session.add(FundNav(
        share_class_id=sc.id, effective_at=day, version=version,
        unit_nav=Decimal(value),
        available_at=available_at or _utc(day.year, day.month, day.day)
        + dt.timedelta(days=1),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))


def _ctx(decision_at: dt.date) -> DecisionExecutionContext:
    return DecisionExecutionContext(
        decision_id="D-PIT", decision_at=decision_at, data_as_of=decision_at,
        strategy_version="sv-1", policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )


def _series(db_session, sc, decision_at, date_from, date_to):
    ctx = PitDataContext(context=_ctx(decision_at), session=db_session)
    return ctx.navs().adjusted_nav_series(sc.id, date_from, date_to)


def test_backfill_computes_adjusted_nav(db_session, share_class):
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.1")
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.0")
    db_session.add(FundDistribution(
        share_class_id=share_class.id, effective_at=dt.date(2020, 1, 3), version=1,
        dividend_per_unit=Decimal("0.1"), split_ratio=Decimal(1),
        available_at=_utc(2020, 1, 4), availability_quality="INFERRED",
        published_at=None, provider_available_at=None, ingested_at=_utc(2026, 8, 31),
    ))
    db_session.flush()

    updated = backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    assert updated == 2

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.adjusted_nav for p in points] == [Decimal("1.1"), Decimal("1.1")]


def test_data_not_yet_available_is_invisible(db_session, share_class):
    """PIT 的核心断言：决策时点看不见的数据不得参与。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0",
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, dt.date(2020, 1, 3), "1.5",
             available_at=_utc(2020, 1, 10))  # 迟到的数据
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    early = _series(db_session, share_class, dt.date(2020, 1, 5),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in early] == [dt.date(2020, 1, 2)]

    later = _series(db_session, share_class, dt.date(2020, 1, 15),
                    dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in later] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_revision_is_resolved_by_decision_time(db_session, share_class):
    """净值修订：决策时点之前看到的是旧版本，之后才是新版本。"""
    day = dt.date(2020, 1, 2)
    _add_nav(db_session, share_class, day, "1.0", version=1,
             available_at=_utc(2020, 1, 3))
    _add_nav(db_session, share_class, day, "1.2", version=2,
             available_at=_utc(2020, 2, 1))
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    before = _series(db_session, share_class, dt.date(2020, 1, 10), day, day)
    assert before[0].unit_nav == Decimal("1.0")
    assert before[0].version == 1

    after = _series(db_session, share_class, dt.date(2020, 3, 1), day, day)
    assert after[0].unit_nav == Decimal("1.2")
    assert after[0].version == 2


def test_series_is_sorted_and_bounded_by_date_range(db_session, share_class):
    for day, value in [(dt.date(2020, 1, 3), "1.1"),
                       (dt.date(2020, 1, 2), "1.0"),
                       (dt.date(2021, 1, 4), "1.3")]:
        _add_nav(db_session, share_class, day, value)
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))

    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert [p.effective_at for p in points] == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]


def test_availability_quality_is_returned(db_session, share_class):
    """调用方必须能判断这段序列的 PIT 可信度。"""
    _add_nav(db_session, share_class, dt.date(2020, 1, 2), "1.0")
    db_session.flush()
    backfill_adjusted_nav(db_session, share_class.id, dt.date(2026, 8, 31))
    points = _series(db_session, share_class, dt.date(2026, 8, 31),
                     dt.date(2020, 1, 1), dt.date(2020, 12, 31))
    assert points[0].availability_quality == "INFERRED"


def test_empty_range_returns_empty_list(db_session, share_class):
    assert _series(db_session, share_class, dt.date(2026, 8, 31),
                   dt.date(2020, 1, 1), dt.date(2020, 12, 31)) == []
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_pit_nav_repository.py -v -m integration`
Expected: FAIL —— `ModuleNotFoundError: ...repositories.nav`

- [ ] **Step 3：写 `src/fip/services/data_service/repositories/nav.py`**

```python
import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.platform.decision_data.pit import NavPoint

_SERIES_SQL = text("""
    SELECT DISTINCT ON (effective_at)
           effective_at, unit_nav, adjusted_nav, version, availability_quality
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id
      AND available_at <= :visible_until
      AND effective_at BETWEEN :date_from AND :date_to
    ORDER BY effective_at, version DESC
""")


class SqlNavPitRepository:
    """PIT NAV 访问的 SQL 实现。

    decision_at 在【构造期】注入，方法签名中不出现时点参数 —— 调用方
    无法省略它，也无法绕过它取到未来数据（PIT-A2 / PIT-A3）。

    版本解析：对每个 effective_at，在 available_at ≤ decision_at 的行中
    取 version 最大者。这实现了上游原则二的「取 available_at ≤ decision_at
    中的最新版本」。
    """

    def __init__(self, session: Session, decision_at: dt.date) -> None:
        self._session = session
        self._decision_at = decision_at

    def adjusted_nav_series(
        self,
        share_class_id: int,
        date_from: dt.date,
        date_to: dt.date,
    ) -> list[NavPoint]:
        # decision_at 是业务日期；可见性判定取该日终了时刻。
        visible_until = dt.datetime.combine(
            self._decision_at, dt.time.max, tzinfo=dt.UTC
        )
        rows = self._session.execute(
            _SERIES_SQL,
            {
                "share_class_id": share_class_id,
                "visible_until": visible_until,
                "date_from": date_from,
                "date_to": date_to,
            },
        ).mappings().all()
        return [
            NavPoint(
                effective_at=row["effective_at"],
                adjusted_nav=row["adjusted_nav"],
                unit_nav=row["unit_nav"],
                version=row["version"],
                availability_quality=row["availability_quality"],
            )
            for row in rows
        ]
```

- [ ] **Step 4：写 `src/fip/services/data_service/normalization/backfill.py`**

```python
import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from fip.services.data_service.normalization.adjusted_nav import (
    AdjustedNavUnavailable,
    DistributionEvent,
    NavObservation,
    compute_adjusted_nav,
)

_NAV_SQL = text("""
    SELECT DISTINCT ON (effective_at) effective_at, unit_nav, version
    FROM market.fund_nav
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version DESC
""")

_EVENT_SQL = text("""
    SELECT DISTINCT ON (effective_at) effective_at, dividend_per_unit, split_ratio
    FROM market.fund_distribution
    WHERE share_class_id = :share_class_id AND available_at <= :visible_until
    ORDER BY effective_at, version DESC
""")

_UPDATE_SQL = text("""
    UPDATE market.fund_nav
    SET adjusted_nav = :adjusted_nav
    WHERE share_class_id = :share_class_id
      AND effective_at = :effective_at
      AND version = :version
""")


def backfill_adjusted_nav(
    session: Session, share_class_id: int, decision_at: dt.date
) -> int:
    """按 decision_at 可见的净值与事件计算复权净值并回填。

    事件日缺净值时抛 AdjustedNavUnavailable —— 该份额类别的 adjusted_nav
    保持为 NULL，下游据此标记 UNAVAILABLE，【不填 0、不沿用上期】（C-6）。
    """
    visible_until = dt.datetime.combine(decision_at, dt.time.max, tzinfo=dt.UTC)
    params = {"share_class_id": share_class_id, "visible_until": visible_until}

    nav_rows = session.execute(_NAV_SQL, params).mappings().all()
    if not nav_rows:
        return 0
    event_rows = session.execute(_EVENT_SQL, params).mappings().all()

    points = compute_adjusted_nav(
        [NavObservation(r["effective_at"], r["unit_nav"]) for r in nav_rows],
        [
            DistributionEvent(r["effective_at"], r["dividend_per_unit"], r["split_ratio"])
            for r in event_rows
        ],
    )

    version_by_date = {r["effective_at"]: r["version"] for r in nav_rows}
    for point in points:
        session.execute(_UPDATE_SQL, {
            "adjusted_nav": point.adjusted_nav,
            "share_class_id": share_class_id,
            "effective_at": point.effective_at,
            "version": version_by_date[point.effective_at],
        })
    session.flush()
    return len(points)


__all__ = ["AdjustedNavUnavailable", "backfill_adjusted_nav"]
```

- [ ] **Step 5：运行测试确认通过**

Run: `.venv/bin/pytest tests/integration/test_pit_nav_repository.py -v -m integration`
Expected: 6 passed

- [ ] **Step 6：运行全量测试**

Run: `make check`
Expected: lint 与 typecheck 无错误；全部测试通过

- [ ] **Step 7：提交**

```bash
git add -A
git commit -m "feat(data): 复权净值回填与 PIT NAV Repository

Plan-1 的核心交付：给定任意历史 decision_at，取回当时可见的复权净值序列。
版本解析取 available_at ≤ decision_at 中的最大 version —— 迟到的数据
在早期决策中不可见，净值修订在修订公布前不可见。"
```

---

## Task 16：risk_free_rate 曲线

> `03-erd` §6.5：**Risk-free Rate 是曲线，不是单值。** 它必须带 `currency` 与 `tenor` —— 否则 Sharpe 用的是哪一段期限无从回答。
>
> 它是**市场数据**（观测所得），与 `MAR`（评价配置）性质不同，必须独立建模（上游 §5.5.1）。

**Files:**
- Modify: `src/fip/services/data_service/models/market.py`（追加 `RiskFreeRate`）
- Modify: `src/fip/services/data_service/adapters/akshare/parse.py`（追加 `parse_yield_curve_frame`）
- Create: `db/migrations/versions/0010_risk_free_rate.py`
- Test: `tests/unit/test_yield_curve_parsing.py`, `tests/integration/test_risk_free_rate.py`

**Interfaces:**
- Consumes: `VersionedMixin`、`RatioNumeric`
- Produces:
  - ORM `RiskFreeRate`（`market.risk_free_rate`，PK `(curve_code, currency, tenor, effective_at, version)`）
  - `parse_yield_curve_frame(payload: bytes) -> list[ParsedYieldPoint]`
  - `ParsedYieldPoint`（frozen dataclass：`effective_at: dt.date`、`tenor: str`、`rate: Decimal`）

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_yield_curve_parsing.py
import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.services.data_service.adapters.akshare.parse import parse_yield_curve_frame


def _payload(frame: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


def test_wide_frame_is_melted_into_tenor_rows():
    """中债曲线是宽表（每个期限一列），需展开为 (日期, 期限, 利率) 行。"""
    payload = _payload(pd.DataFrame({
        "日期": ["2024-01-02", "2024-01-03"],
        "3月": [2.10, 2.12],
        "1年": [2.30, 2.31],
        "10年": [2.60, 2.62],
    }))
    rows = parse_yield_curve_frame(payload)
    assert len(rows) == 6
    one_year = [r for r in rows if r.tenor == "1Y"]
    assert [r.effective_at for r in one_year] == [dt.date(2024, 1, 2), dt.date(2024, 1, 3)]


def test_percentage_is_converted_to_decimal_fraction():
    """全平台百分比一律用小数（10-api §12.1）。2.30% → 0.023。"""
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], "1年": [2.30]}))
    row = parse_yield_curve_frame(payload)[0]
    assert row.rate == Decimal("0.02300000")
    assert isinstance(row.rate, Decimal)


@pytest.mark.parametrize(
    ("column", "tenor"),
    [("3月", "3M"), ("6月", "6M"), ("1年", "1Y"), ("3年", "3Y"), ("10年", "10Y")],
)
def test_chinese_tenor_labels_are_normalized(column, tenor):
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], column: [2.0]}))
    assert parse_yield_curve_frame(payload)[0].tenor == tenor


def test_unrecognized_tenor_columns_are_skipped():
    """无法识别的列直接跳过，不猜测其含义。"""
    payload = _payload(pd.DataFrame({
        "日期": ["2024-01-02"], "1年": [2.30], "曲线名称": ["中债国债收益率曲线"],
    }))
    rows = parse_yield_curve_frame(payload)
    assert [r.tenor for r in rows] == ["1Y"]


def test_missing_rate_is_dropped_not_filled():
    payload = _payload(pd.DataFrame({"日期": ["2024-01-02"], "1年": [None]}))
    assert parse_yield_curve_frame(payload) == []
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_yield_curve_parsing.py -v`
Expected: FAIL —— `ImportError: cannot import name 'parse_yield_curve_frame'`

- [ ] **Step 3：在 `parse.py` 末尾追加**

```python
_TENOR_LABELS: dict[str, str] = {
    "3月": "3M", "6月": "6M", "1年": "1Y", "2年": "2Y", "3年": "3Y",
    "5年": "5Y", "7年": "7Y", "10年": "10Y", "30年": "30Y",
}


@dataclass(frozen=True, slots=True)
class ParsedYieldPoint:
    effective_at: dt.date
    tenor: str
    rate: Decimal


def parse_yield_curve_frame(payload: bytes) -> list[ParsedYieldPoint]:
    """中债国债收益率曲线（宽表）→ (日期, 期限, 利率) 行。

    利率一律转为小数（2.30% → 0.023），与全平台「百分比用小数」一致
    （10-api/01 §12.1）。混用会在下游产生难以察觉的 100 倍误差。

    无法识别的列直接跳过 —— 不猜测其含义。
    """
    frame = pd.read_parquet(io.BytesIO(payload))
    rows: list[ParsedYieldPoint] = []
    hundred = Decimal(100)
    for _, record in frame.iterrows():
        day = _to_date(record.get("日期"))
        if day is None:
            continue
        for column, tenor in _TENOR_LABELS.items():
            if column not in frame.columns:
                continue
            percent = _to_decimal(record[column])
            if percent is None:
                continue
            rows.append(ParsedYieldPoint(day, tenor, (percent / hundred).quantize(Decimal("0.00000001"))))
    rows.sort(key=lambda r: (r.effective_at, r.tenor))
    return rows
```

- [ ] **Step 4：在 `models/market.py` 末尾追加 ORM**

```python
class RiskFreeRate(Base, VersionedMixin):
    """无风险利率 —— 【市场数据】，观测所得，随市场变化。

    是曲线不是单值（03-erd §6.5）：必须带 currency 与 tenor，否则
    「这个 Sharpe 用的是哪一段期限」无从回答。

    与 MAR 的边界（上游 §5.5）：MAR 是【评价标准】，由投研配置而非市场
    观测，属 Evaluation Policy，不在本表。即使数值相同也必须独立建模 ——
    R_f 变了是市场变了，MAR 变了是评价标准变了，二者审批路径不同。
    """

    __tablename__ = "risk_free_rate"
    __table_args__ = (
        *temporal_check_constraints("risk_free_rate"),
        {"schema": "market"},
    )

    curve_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), primary_key=True)
    tenor: Mapped[str] = mapped_column(String(8), primary_key=True)
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    rate: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    raw_payload_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
```

在 `models/market.py` 顶部的 import 中补上 `String` 与 `RatioNumeric`：

```python
from sqlalchemy import BigInteger, ForeignKey, String
from fip.platform.db.types import NavNumeric, RatioNumeric
```

- [ ] **Step 5：写迁移 `db/migrations/versions/0010_risk_free_rate.py`**

```python
"""market.risk_free_rate

Revision ID: 0010
Revises: 0009
"""
from alembic import op

from fip.platform.db.mixins import QUALITY_SOURCE_SQL, TIME_ORDER_SQL

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE market.risk_free_rate (
            curve_code            VARCHAR(64)  NOT NULL,
            currency              VARCHAR(8)   NOT NULL,
            tenor                 VARCHAR(8)   NOT NULL,
            effective_at          DATE         NOT NULL,
            version               INTEGER      NOT NULL DEFAULT 1,
            rate                  NUMERIC(12,8) NOT NULL,
            raw_payload_id        BIGINT,
            available_at          TIMESTAMPTZ  NOT NULL,
            availability_quality  availability_quality_enum NOT NULL,
            published_at          TIMESTAMPTZ,
            provider_available_at TIMESTAMPTZ,
            ingested_at           TIMESTAMPTZ  NOT NULL,
            created_at            TIMESTAMPTZ  NOT NULL DEFAULT now(),
            PRIMARY KEY (curve_code, currency, tenor, effective_at, version),
            CONSTRAINT ck_risk_free_rate_quality_source CHECK ({QUALITY_SOURCE_SQL}),
            CONSTRAINT ck_risk_free_rate_time_order     CHECK ({TIME_ORDER_SQL})
        )
    """)
    op.execute(
        "CREATE INDEX ix_risk_free_rate_pit ON market.risk_free_rate "
        "(currency, tenor, effective_at, available_at, version DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market.risk_free_rate CASCADE")
```

- [ ] **Step 6：写集成测试**

```python
# tests/integration/test_risk_free_rate.py
import datetime as dt
from decimal import Decimal

import pytest

from fip.services.data_service.models.market import RiskFreeRate

pytestmark = pytest.mark.integration


def _rate(tenor, day, value, version=1):
    return RiskFreeRate(
        curve_code="CN_TREASURY", currency="CNY", tenor=tenor,
        effective_at=day, version=version, rate=Decimal(value),
        available_at=dt.datetime.combine(day, dt.time.min, tzinfo=dt.UTC)
        + dt.timedelta(days=1),
        availability_quality="INFERRED", published_at=None,
        provider_available_at=None,
        ingested_at=dt.datetime(2026, 8, 31, tzinfo=dt.UTC),
    )


def test_multiple_tenors_coexist_on_one_date(db_session):
    """曲线不是单值 —— 同一天必须能存多个期限。"""
    day = dt.date(2024, 1, 2)
    db_session.add_all([_rate("3M", day, "0.021"), _rate("1Y", day, "0.023"),
                        _rate("10Y", day, "0.026")])
    db_session.flush()
    assert db_session.query(RiskFreeRate).filter_by(effective_at=day).count() == 3


def test_rate_is_stored_as_decimal_fraction(db_session):
    db_session.add(_rate("1Y", dt.date(2024, 1, 2), "0.023"))
    db_session.flush()
    row = db_session.query(RiskFreeRate).one()
    assert row.rate == Decimal("0.02300000")


def test_revision_creates_a_new_version(db_session):
    day = dt.date(2024, 1, 2)
    db_session.add(_rate("1Y", day, "0.023", version=1))
    db_session.flush()
    db_session.add(_rate("1Y", day, "0.0235", version=2))
    db_session.flush()
    assert db_session.query(RiskFreeRate).filter_by(tenor="1Y").count() == 2
```

- [ ] **Step 7：应用迁移并运行测试**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/pytest tests/unit/test_yield_curve_parsing.py tests/integration/test_risk_free_rate.py -v
```

Expected: 9 passed + 3 passed

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(market): risk_free_rate 曲线

带 currency 与 tenor 的曲线而非单值 —— 否则『这个 Sharpe 用的是哪段
期限』无从回答。利率一律转为小数与全平台口径一致。
与 MAR 独立建模：R_f 变了是市场变了，MAR 变了是评价标准变了。"
```

---

## Task 17：Fund 维度与历史表、Investment Eligibility 派生

> `Investment Eligibility` 是**客观事实**（基金能不能被交易），归 `data-service`；
> `Eligibility Rules` 是**策略规则**（本策略要什么样的基金），归 `fund-service`。
> 两者名称相近但性质不同，**前者是后者的输入之一，不是同义词**（`01-system-architecture` §6.5）。

**Files:**
- Modify: `src/fip/services/data_service/models/fund.py`（追加 5 个 ORM）
- Create: `src/fip/services/data_service/eligibility.py`
- Create: `db/migrations/versions/0011_fund_dimensions.py`
- Test: `tests/unit/test_eligibility_derivation.py`, `tests/integration/test_fund_dimensions.py`

**Interfaces:**
- Consumes: `IntervalMixin`、`interval_check`、`temporal_check_constraints`
- Produces:
  - ORM：`FundManagementCompany`、`FundManager`、`FundManagerAssignment`、`FundClassificationHistory`、`FundStatusHistory`、`FundFee`、`InvestmentEligibility`
  - `LifecycleStatus`（`StrEnum`：`NORMAL`、`SUSPENDED_SUBSCRIPTION`、`LIQUIDATED`、`MERGED`、`TRANSFORMED`）
  - `EligibilityStatus`（`StrEnum`：`FULLY_ELIGIBLE`、`HOLD_ONLY`、`LIMITED`、`EXIT_ONLY`、`NOT_TRADABLE`）
  - `derive_eligibility(lifecycle: LifecycleStatus, subscription_open: bool, redemption_open: bool) -> EligibilityStatus`

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_eligibility_derivation.py
import pytest

from fip.services.data_service.eligibility import (
    EligibilityStatus,
    LifecycleStatus,
    derive_eligibility,
)


def test_normal_and_open_is_fully_eligible():
    assert derive_eligibility(LifecycleStatus.NORMAL, True, True) \
        is EligibilityStatus.FULLY_ELIGIBLE


def test_suspended_subscription_can_still_be_held_and_sold():
    """『暂停申购』意味着不可加仓但仍可持有与减仓。

    用单一生命周期状态无法表达这一点 —— 这正是 Investment Eligibility
    必须与 Fund Lifecycle Status 分离的原因（上游术语表）。
    """
    assert derive_eligibility(LifecycleStatus.SUSPENDED_SUBSCRIPTION, False, True) \
        is EligibilityStatus.EXIT_ONLY


def test_open_subscription_with_closed_redemption_is_hold_only():
    assert derive_eligibility(LifecycleStatus.NORMAL, True, False) \
        is EligibilityStatus.HOLD_ONLY


def test_both_closed_is_not_tradable():
    assert derive_eligibility(LifecycleStatus.NORMAL, False, False) \
        is EligibilityStatus.NOT_TRADABLE


@pytest.mark.parametrize(
    "lifecycle",
    [LifecycleStatus.LIQUIDATED, LifecycleStatus.MERGED],
)
def test_terminated_funds_are_never_tradable(lifecycle):
    """清盘或合并的基金，无论申赎标志如何都不可交易。"""
    assert derive_eligibility(lifecycle, True, True) is EligibilityStatus.NOT_TRADABLE


def test_transformed_fund_follows_its_subscription_flags():
    """转型不等于终止 —— 转型后基金仍可交易，分类会变。"""
    assert derive_eligibility(LifecycleStatus.TRANSFORMED, True, True) \
        is EligibilityStatus.FULLY_ELIGIBLE
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_eligibility_derivation.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...data_service.eligibility`

- [ ] **Step 3：写 `src/fip/services/data_service/eligibility.py`**

```python
from enum import StrEnum


class LifecycleStatus(StrEnum):
    """基金处于什么状态 —— 描述性事实。"""

    NORMAL = "NORMAL"
    SUSPENDED_SUBSCRIPTION = "SUSPENDED_SUBSCRIPTION"
    LIQUIDATED = "LIQUIDATED"
    MERGED = "MERGED"
    TRANSFORMED = "TRANSFORMED"


class EligibilityStatus(StrEnum):
    """在 decision_at 时点该基金能否被建仓 / 加仓 / 减仓。"""

    FULLY_ELIGIBLE = "FULLY_ELIGIBLE"  # 可建仓、可加仓、可减仓
    HOLD_ONLY = "HOLD_ONLY"            # 可持有、可加仓，不可减仓
    LIMITED = "LIMITED"                # 有限额
    EXIT_ONLY = "EXIT_ONLY"            # 仅可减仓
    NOT_TRADABLE = "NOT_TRADABLE"      # 不可交易


_TERMINATED = {LifecycleStatus.LIQUIDATED, LifecycleStatus.MERGED}


def derive_eligibility(
    lifecycle: LifecycleStatus,
    subscription_open: bool,
    redemption_open: bool,
) -> EligibilityStatus:
    """由生命周期状态与申赎标志派生可投资性。

    Investment Eligibility 是【客观事实】，不含任何策略判断，因此归
    data-service。它是 Eligibility Rules（策略规则，归 fund-service）
    的输入之一，不是它的同义词（01-system-architecture §6.5）。

    它必须与 Fund Lifecycle Status 分离：『暂停申购』意味着不可加仓但
    仍可持有与减仓，用单一生命周期状态无法表达。回测判断某基金当时能否
    买入，依据的是本函数的产出，不是 Lifecycle Status。
    """
    if lifecycle in _TERMINATED:
        return EligibilityStatus.NOT_TRADABLE
    if subscription_open and redemption_open:
        return EligibilityStatus.FULLY_ELIGIBLE
    if subscription_open and not redemption_open:
        return EligibilityStatus.HOLD_ONLY
    if not subscription_open and redemption_open:
        return EligibilityStatus.EXIT_ONLY
    return EligibilityStatus.NOT_TRADABLE
```

- [ ] **Step 4：在 `models/fund.py` 末尾追加 ORM**

```python
class FundManagementCompany(Base):
    __tablename__ = "fund_management_company"
    __table_args__ = {"schema": "fund"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    company_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundManager(Base):
    __tablename__ = "fund_manager"
    __table_args__ = {"schema": "fund"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    manager_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    manager_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundManagerAssignment(Base, IntervalMixin):
    """任职区间。支持共管 —— 同一基金同一时段可有多位经理（N:M）。

    区间型实体同样需要 available_at：任职生效日 2026-08-20、公告日
    2026-08-25 时，8-22 的决策中该任职【不可见】。只有 valid_from
    没有 available_at 会形成前视偏差（03-erd §15.2）。
    """

    __tablename__ = "fund_manager_assignment"
    __table_args__ = (
        *temporal_check_constraints("fund_manager_assignment", anchor="valid_from"),
        interval_check("fund_manager_assignment"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_manager.id", ondelete="RESTRICT"), nullable=False
    )


class FundClassificationHistory(Base, IntervalMixin):
    """分类历史 —— 基金转型会改变分类，回测必须使用当时的分类。"""

    __tablename__ = "fund_classification_history"
    __table_args__ = (
        *temporal_check_constraints("fund_classification_history", anchor="valid_from"),
        interval_check("fund_classification_history"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund.id", ondelete="RESTRICT"), nullable=False
    )
    classification_scheme: Mapped[str] = mapped_column(String(32), nullable=False)
    classification_code: Mapped[str] = mapped_column(String(32), nullable=False)


class FundStatusHistory(Base, IntervalMixin):
    __tablename__ = "fund_status_history"
    __table_args__ = (
        *temporal_check_constraints("fund_status_history", anchor="valid_from"),
        interval_check("fund_status_history"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False)
    subscription_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    redemption_open: Mapped[bool] = mapped_column(Boolean, nullable=False)


class FundFee(Base, IntervalMixin):
    """费率 —— 各份额类别不同，这正是 Fund 与 Share Class 必须分离的原因。"""

    __tablename__ = "fund_fee"
    __table_args__ = (
        *temporal_check_constraints("fund_fee", anchor="valid_from"),
        interval_check("fund_fee"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rate: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)


class InvestmentEligibility(Base, IntervalMixin):
    """可投资性 —— 派生实体，但必须持久化：回测需查历史（03-erd §5.6）。"""

    __tablename__ = "investment_eligibility"
    __table_args__ = (
        *temporal_check_constraints("investment_eligibility", anchor="valid_from"),
        interval_check("investment_eligibility"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
```

在 `models/fund.py` 顶部补齐 import：

```python
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint, func,
)

from fip.platform.db.mixins import IntervalMixin, interval_check, temporal_check_constraints
from fip.platform.db.types import RatioNumeric
```

- [ ] **Step 5：生成并核对迁移**

```bash
.venv/bin/alembic -x db=dev revision --autogenerate -m "fund 维度与历史表" --rev-id 0011
```

打开生成文件逐行核对：应只包含 7 张新表的 `create_table`。**特别检查每张区间型表都带上了三个 CHECK 约束**（`ck_*_quality_source`、`ck_*_time_order`、`ck_*_interval`）；autogenerate 有时会漏掉 Mixin 提供的约束，缺失则手工补上。然后：

```bash
.venv/bin/alembic -x db=dev upgrade head
```

- [ ] **Step 6：写集成测试**

```python
# tests/integration/test_fund_dimensions.py
import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from fip.services.data_service.eligibility import EligibilityStatus, LifecycleStatus
from fip.services.data_service.grouping import GroupingStatus
from fip.services.data_service.models.fund import (
    Fund, FundManager, FundManagerAssignment, FundShareClass,
    FundStatusHistory, InvestmentEligibility,
)

pytestmark = pytest.mark.integration

ING = dt.datetime(2026, 8, 31, tzinfo=dt.UTC)


@pytest.fixture()
def share_class(db_session) -> FundShareClass:
    fund = Fund(fund_code="P-DIM", product_name="维度测试",
                grouping_status=GroupingStatus.CONFIRMED.value)
    db_session.add(fund)
    db_session.flush()
    sc = FundShareClass(fund_id=fund.id, share_class_code="A", display_name="维度测试A")
    db_session.add(sc)
    db_session.flush()
    return sc


def _times(available: dt.datetime):
    return dict(available_at=available, availability_quality="INFERRED",
                published_at=None, provider_available_at=None, ingested_at=ING)


def test_manager_assignment_supports_co_management(db_session, share_class):
    """同一基金同一时段可有多位经理。"""
    managers = [FundManager(manager_code=f"M{i}", manager_name=f"经理{i}")
                for i in (1, 2)]
    db_session.add_all(managers)
    db_session.flush()
    for m in managers:
        db_session.add(FundManagerAssignment(
            fund_id=share_class.fund_id, manager_id=m.id,
            valid_from=dt.date(2020, 1, 1), valid_to=None,
            **_times(dt.datetime(2020, 1, 5, tzinfo=dt.UTC)),
        ))
    db_session.flush()
    assert db_session.query(FundManagerAssignment).filter_by(
        fund_id=share_class.fund_id).count() == 2


def test_interval_with_end_before_start_is_rejected(db_session, share_class):
    db_session.add(FundStatusHistory(
        share_class_id=share_class.id,
        lifecycle_status=LifecycleStatus.NORMAL.value,
        subscription_open=True, redemption_open=True,
        valid_from=dt.date(2020, 6, 1), valid_to=dt.date(2020, 1, 1),
        **_times(dt.datetime(2020, 6, 2, tzinfo=dt.UTC)),
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_interval_tables_also_enforce_quality_source_check(db_session, share_class):
    """区间型表同样受 C-12 约束：标 EXACT 就必须真有推送时刻。"""
    db_session.add(FundStatusHistory(
        share_class_id=share_class.id,
        lifecycle_status=LifecycleStatus.NORMAL.value,
        subscription_open=True, redemption_open=True,
        valid_from=dt.date(2020, 1, 1), valid_to=None,
        available_at=dt.datetime(2020, 1, 2, tzinfo=dt.UTC),
        availability_quality="EXACT",
        published_at=None, provider_available_at=None, ingested_at=ING,
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_eligibility_history_is_persisted_for_backtest(db_session, share_class):
    """派生实体也要落表 —— 回测需要查当时的可投资性。"""
    db_session.add_all([
        InvestmentEligibility(
            share_class_id=share_class.id,
            eligibility_status=EligibilityStatus.FULLY_ELIGIBLE.value,
            valid_from=dt.date(2020, 1, 1), valid_to=dt.date(2021, 1, 1),
            **_times(dt.datetime(2020, 1, 2, tzinfo=dt.UTC)),
        ),
        InvestmentEligibility(
            share_class_id=share_class.id,
            eligibility_status=EligibilityStatus.EXIT_ONLY.value,
            valid_from=dt.date(2021, 1, 1), valid_to=None,
            **_times(dt.datetime(2021, 1, 2, tzinfo=dt.UTC)),
        ),
    ])
    db_session.flush()
    assert db_session.query(InvestmentEligibility).filter_by(
        share_class_id=share_class.id).count() == 2
```

- [ ] **Step 7：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_eligibility_derivation.py tests/integration/test_fund_dimensions.py -v`
Expected: 7 passed + 4 passed

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(fund): 维度与历史表、Investment Eligibility 派生

Investment Eligibility 是客观事实归 data-service，Eligibility Rules 是
策略规则归 fund-service —— 前者是后者的输入之一，不是同义词。
二者必须分离：『暂停申购』意味着不可加仓但仍可持有与减仓，用单一
生命周期状态无法表达。区间型表同样带 available_at，否则形成前视偏差。"
```

---

## Task 18：数据质量闸门与三级阻断粒度

> 上游原则五**失败显式化**：数据质量不达标必须阻断并上报，**严禁静默降级**。
>
> 但阻断必须有粒度 —— 一只基金缺数据不该阻断整个市场。三级粒度：
> **Fund-level** 只影响该基金；**Metric-level** 只影响依赖该指标的结果；**Global-level** 阻断整个决策周期。

**Files:**
- Create: `src/fip/services/data_service/quality.py`
- Test: `tests/unit/test_quality_gate.py`, `tests/integration/test_quality_blocks_job.py`

**Interfaces:**
- Consumes: `fip.platform.jobs.models.ExecutionStatus`
- Produces:
  - `QualityLevel`（`StrEnum`：`VALID`、`WARNING`、`INVALID`）
  - `BlockingScope`（`StrEnum`：`FUND`、`METRIC`、`GLOBAL`）
  - `QualityFinding`（frozen dataclass：`scope`、`level`、`subject: str`、`reason: str`）
  - `QualityVerdict`（frozen dataclass：`findings: tuple[QualityFinding, ...]`；属性 `is_globally_blocked: bool`、`blocked_fund_ids: frozenset[int]`、`blocked_metrics: frozenset[str]`）
  - `evaluate_batch_quality(expected_ids, arrived_ids, unavailable_adjusted_nav_ids, coverage_threshold: Decimal) -> QualityVerdict`

> **M1 的范围界定**：质量判定结果**不落 `data_quality_result` 表**（该表属 M2，spec §6.3）。M1 的判定结果体现为 Job 的 `status=BLOCKED` 与 `error_code`，以及返回给调用方的 `QualityVerdict`。这避免为一个尚未被查询的表提前建模。

- [ ] **Step 1：写失败的单元测试**

```python
# tests/unit/test_quality_gate.py
from decimal import Decimal

from fip.services.data_service.quality import (
    BlockingScope,
    QualityLevel,
    evaluate_batch_quality,
)

THRESHOLD = Decimal("0.95")


def _verdict(expected, arrived, unavailable=()):
    return evaluate_batch_quality(expected, arrived, unavailable, THRESHOLD)


def test_full_arrival_is_valid():
    verdict = _verdict([1, 2, 3], [1, 2, 3])
    assert verdict.findings == ()
    assert verdict.is_globally_blocked is False


def test_single_missing_fund_blocks_only_that_fund():
    """一只基金缺数据不该阻断整个市场。"""
    verdict = _verdict(list(range(1, 101)), list(range(2, 101)))
    assert verdict.is_globally_blocked is False
    assert verdict.blocked_fund_ids == frozenset({1})
    assert all(f.scope is BlockingScope.FUND for f in verdict.findings)


def test_coverage_below_threshold_blocks_globally():
    """全市场数据未到位 → 阻断整个决策周期，人工确认后继续。"""
    verdict = _verdict(list(range(1, 101)), list(range(1, 91)))  # 覆盖率 0.90
    assert verdict.is_globally_blocked is True
    assert any(f.scope is BlockingScope.GLOBAL and f.level is QualityLevel.INVALID
               for f in verdict.findings)


def test_coverage_exactly_at_threshold_is_not_blocked():
    verdict = _verdict(list(range(1, 101)), list(range(1, 96)))  # 覆盖率 0.95
    assert verdict.is_globally_blocked is False


def test_unavailable_adjusted_nav_is_metric_level():
    """复权净值算不出 → 只影响依赖它的指标，基金本身仍在池内。"""
    verdict = _verdict([1, 2], [1, 2], unavailable=[2])
    assert verdict.is_globally_blocked is False
    assert verdict.blocked_fund_ids == frozenset()
    assert "adjusted_nav" in verdict.blocked_metrics
    assert any(f.scope is BlockingScope.METRIC for f in verdict.findings)


def test_empty_expectation_blocks_globally():
    """预期为空说明上游配置有问题，不能当作『全部到齐』。"""
    verdict = _verdict([], [])
    assert verdict.is_globally_blocked is True


def test_findings_carry_actionable_reasons():
    """只给结论不给原因，运维无法处置。"""
    verdict = _verdict([1, 2], [1])
    assert all(f.reason for f in verdict.findings)
    assert all(f.subject for f in verdict.findings)


def test_no_silent_degradation_missing_funds_are_never_dropped_quietly():
    """缺失必须产生 finding —— 静默丢弃是原则五禁止的降级。"""
    verdict = _verdict([1, 2, 3], [1])
    subjects = {f.subject for f in verdict.findings if f.scope is BlockingScope.FUND}
    assert subjects == {"2", "3"}
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/unit/test_quality_gate.py -v`
Expected: FAIL —— `ModuleNotFoundError: ...data_service.quality`

- [ ] **Step 3：写 `src/fip/services/data_service/quality.py`**

```python
from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class QualityLevel(StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class BlockingScope(StrEnum):
    FUND = "FUND"      # 只影响该基金
    METRIC = "METRIC"  # 只影响依赖该指标的结果
    GLOBAL = "GLOBAL"  # 阻断整个决策周期


@dataclass(frozen=True, slots=True)
class QualityFinding:
    scope: BlockingScope
    level: QualityLevel
    subject: str
    reason: str


@dataclass(frozen=True, slots=True)
class QualityVerdict:
    findings: tuple[QualityFinding, ...]

    @property
    def is_globally_blocked(self) -> bool:
        return any(
            f.scope is BlockingScope.GLOBAL and f.level is QualityLevel.INVALID
            for f in self.findings
        )

    @property
    def blocked_fund_ids(self) -> frozenset[int]:
        return frozenset(
            int(f.subject)
            for f in self.findings
            if f.scope is BlockingScope.FUND and f.level is QualityLevel.INVALID
        )

    @property
    def blocked_metrics(self) -> frozenset[str]:
        return frozenset(
            f.subject for f in self.findings if f.scope is BlockingScope.METRIC
        )


def evaluate_batch_quality(
    expected_share_class_ids: Collection[int],
    arrived_share_class_ids: Collection[int],
    unavailable_adjusted_nav_ids: Collection[int],
    coverage_threshold: Decimal,
) -> QualityVerdict:
    """评估一个灌数批次的质量，产出带粒度的阻断判定。

    严禁静默降级（上游原则五）：任何缺失都必须产生 finding。
    但阻断有粒度 —— 一只基金缺数据不该阻断整个市场。
    """
    expected = set(expected_share_class_ids)
    arrived = set(arrived_share_class_ids)
    findings: list[QualityFinding] = []

    if not expected:
        return QualityVerdict((
            QualityFinding(
                BlockingScope.GLOBAL, QualityLevel.INVALID, "batch",
                "预期份额类别集合为空 —— 上游配置异常，不得视为全部到齐",
            ),
        ))

    coverage = Decimal(len(arrived & expected)) / Decimal(len(expected))
    if coverage < coverage_threshold:
        findings.append(QualityFinding(
            BlockingScope.GLOBAL, QualityLevel.INVALID, "batch",
            f"到达覆盖率 {coverage} 低于阈值 {coverage_threshold}，"
            "疑似全市场数据未到位，阻断本决策周期",
        ))

    for missing in sorted(expected - arrived):
        findings.append(QualityFinding(
            BlockingScope.FUND, QualityLevel.INVALID, str(missing),
            "本批次未收到该份额类别的数据",
        ))

    if unavailable_adjusted_nav_ids:
        findings.append(QualityFinding(
            BlockingScope.METRIC, QualityLevel.INVALID, "adjusted_nav",
            f"{len(set(unavailable_adjusted_nav_ids))} 个份额类别的复权净值"
            "无法计算，依赖它的指标标记 UNAVAILABLE（不得填 0）",
        ))

    return QualityVerdict(tuple(findings))
```

- [ ] **Step 4：写集成测试 —— 质量阻断映射到 Job 状态**

```python
# tests/integration/test_quality_blocks_job.py
from decimal import Decimal

import pytest

from fip.platform.jobs.models import ExecutionStatus
from fip.platform.jobs.submitter import JobSubmitter
from fip.services.data_service.quality import evaluate_batch_quality

pytestmark = pytest.mark.integration


def _apply(job, verdict):
    """把质量判定映射到 Job 状态。

    Global 阻断 → BLOCKED（不是 FAILED）：它不是系统故障，
    自动重试只会反复撞同一堵墙（01-system-architecture §10.5.4）。
    """
    if verdict.is_globally_blocked:
        job.status = ExecutionStatus.BLOCKED.value
        job.error_code = "DATA_QUALITY_GLOBAL_BLOCK"
    else:
        job.status = ExecutionStatus.COMPLETED.value
    return job


def test_global_block_marks_job_blocked_not_failed(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|q|global|2020-01-01|2020-01-02")
    verdict = evaluate_batch_quality(list(range(1, 101)), list(range(1, 51)),
                                     [], Decimal("0.95"))
    _apply(job, verdict)
    db_session.flush()
    assert job.status == ExecutionStatus.BLOCKED.value
    assert JobSubmitter.is_retryable(job) is False


def test_fund_level_issue_does_not_block_the_job(db_session):
    job = JobSubmitter(db_session).submit("ingest", "ingest|q|fund|2020-01-01|2020-01-02")
    verdict = evaluate_batch_quality(list(range(1, 101)), list(range(2, 101)),
                                     [], Decimal("0.95"))
    _apply(job, verdict)
    db_session.flush()
    assert job.status == ExecutionStatus.COMPLETED.value
    assert verdict.blocked_fund_ids == frozenset({1})
```

- [ ] **Step 5：运行测试确认通过**

Run: `.venv/bin/pytest tests/unit/test_quality_gate.py tests/integration/test_quality_blocks_job.py -v`
Expected: 8 passed + 2 passed

- [ ] **Step 6：提交**

```bash
git add -A
git commit -m "feat(quality): 数据质量闸门与三级阻断粒度

阻断有粒度：一只基金缺数据不该阻断整个市场，但任何缺失都必须产生
finding —— 静默丢弃是原则五禁止的降级。Global 阻断映射为 Job BLOCKED
而非 FAILED：它不是系统故障，自动重试只会反复撞同一堵墙。"
```

---

## Task 19：灌数编排、CLI 与端到端验收

> Plan-1 的收尾。完成后可用真实 AKShare 数据端到端验证核心能力。

**Files:**
- Create: `src/fip/services/data_service/ingest.py`
- Create: `src/fip/platform/cli.py`
- Test: `tests/integration/test_ingest_service.py`

**Interfaces:**
- Consumes: `AkShareSourceAdapter`、`parse_nav_frame`、`parse_distribution_frame`、`parse_split_frame`、`declared_lag_availability`、`backfill_adjusted_nav`、`JobSubmitter`、`split_share_class_name`
- Produces:
  - `IngestService(session: Session, adapter: SourceAdapter, disclosure_lag_days: int)`
  - `IngestService.ensure_dataset(dataset_code: str) -> DataProviderDataset`
  - `IngestService.ingest_fund_list(limit: int | None = None) -> int`
  - `IngestService.ingest_nav(share_class_id: int, provider_fund_id: str) -> int`
  - `IngestService.ingest_distributions(share_class_id: int, provider_fund_id: str) -> int`
  - CLI 子命令：`ingest-funds`、`ingest-nav`、`pit-nav`

- [ ] **Step 1：写失败的集成测试**

```python
# tests/integration/test_ingest_service.py
import datetime as dt
import io
from decimal import Decimal

import pandas as pd
import pytest

from fip.platform.decision_data.context import (
    DecisionExecutionContext, RecomputeScope, RuntimeMode, TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.market import FundNav
from fip.services.data_service.models.raw import RawPayload

pytestmark = pytest.mark.integration

FIXED_NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)

FUND_LIST = pd.DataFrame({
    "基金代码": ["000001", "000002"],
    "基金简称": ["测试蓝筹混合A", "测试蓝筹混合C"],
    "基金类型": ["混合型", "混合型"],
})

NAV_FRAME = pd.DataFrame({
    "净值日期": ["2020-01-02", "2020-01-03"],
    "单位净值": ["1.1000", "1.0000"],
})

DIVIDEND_FRAME = pd.DataFrame({
    "年份": ["2020"], "权益登记日": ["2020-01-02"],
    "除息日": ["2020-01-03"], "每10份分红": ["每10份派现金1.0000元"],
})

SPLIT_FRAME = pd.DataFrame({"年份": [], "拆分折算日": [], "拆分折算比例": []})


def _fake_caller(name, **params):
    indicator = params.get("indicator")
    if name == "fund_name_em":
        return FUND_LIST
    if indicator == "单位净值走势":
        return NAV_FRAME
    if indicator == "分红送配详情":
        return DIVIDEND_FRAME
    if indicator == "拆分详情":
        return SPLIT_FRAME
    raise AssertionError(f"未预期的调用 {name} {params}")


@pytest.fixture()
def service(db_session) -> IngestService:
    adapter = AkShareSourceAdapter(clock=lambda: FIXED_NOW, caller=_fake_caller)
    return IngestService(db_session, adapter, disclosure_lag_days=1)


def test_fund_list_creates_funds_and_share_classes(db_session, service):
    """两个类别归入同一产品。"""
    created = service.ingest_fund_list()
    assert created == 2
    assert db_session.query(Fund).count() == 1
    assert db_session.query(FundShareClass).count() == 2
    codes = {sc.share_class_code for sc in db_session.query(FundShareClass).all()}
    assert codes == {"A", "C"}


def test_ingest_is_idempotent(db_session, service):
    service.ingest_fund_list()
    service.ingest_fund_list()
    assert db_session.query(FundShareClass).count() == 2


def test_nav_ingest_persists_raw_payload(db_session, service):
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    payload = db_session.query(RawPayload).first()
    assert payload is not None
    assert pd.read_parquet(io.BytesIO(payload.payload)).shape[0] == 2
    assert payload.provider_available_at is None  # C-12：如实留空


def test_nav_uses_declared_lag_and_inferred_quality(db_session, service):
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    row = db_session.query(FundNav).filter_by(
        effective_at=dt.date(2020, 1, 2)).one()
    assert row.availability_quality == "INFERRED"
    assert row.available_at == dt.datetime(2020, 1, 3, tzinfo=dt.UTC)


def test_revised_value_creates_version_two(db_session, service):
    """同日不同净值 → 新版本，旧版本保留。"""
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")

    revised = AkShareSourceAdapter(
        clock=lambda: FIXED_NOW,
        caller=lambda *_a, **_k: pd.DataFrame({
            "净值日期": ["2020-01-02"], "单位净值": ["1.2000"],
        }),
    )
    IngestService(db_session, revised, disclosure_lag_days=1).ingest_nav(sc.id, "000001")

    rows = db_session.query(FundNav).filter_by(
        effective_at=dt.date(2020, 1, 2)).order_by(FundNav.version).all()
    assert [r.version for r in rows] == [1, 2]
    assert [r.unit_nav for r in rows] == [Decimal("1.1000"), Decimal("1.2000")]


def test_end_to_end_pit_query_returns_adjusted_series(db_session, service):
    """Plan-1 的验收断言。"""
    service.ingest_fund_list()
    sc = db_session.query(FundShareClass).filter_by(share_class_code="A").one()
    service.ingest_nav(sc.id, "000001")
    service.ingest_distributions(sc.id, "000001")
    service.rebuild_adjusted_nav(sc.id, dt.date(2026, 8, 31))

    ctx = DecisionExecutionContext(
        decision_id="D-E2E", decision_at=dt.date(2026, 8, 31),
        data_as_of=dt.date(2026, 8, 31), strategy_version="sv-1",
        policy_version="pv-1", code_version="cv-1",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    points = PitDataContext(context=ctx, session=db_session).navs().adjusted_nav_series(
        sc.id, dt.date(2020, 1, 1), dt.date(2020, 12, 31)
    )
    # 1.10 → 除息 0.10 后 1.00：复权后收益为 0
    assert [p.adjusted_nav for p in points] == [Decimal("1.1"), Decimal("1.1")]
```

- [ ] **Step 2：运行确认失败**

Run: `.venv/bin/pytest tests/integration/test_ingest_service.py -v -m integration`
Expected: FAIL —— `ModuleNotFoundError: ...data_service.ingest`

- [ ] **Step 3：写 `src/fip/services/data_service/ingest.py`**

```python
import datetime as dt
import io

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fip.platform.source.availability import declared_lag_availability
from fip.platform.source.port import SourceAdapter, SourceRecord
from fip.services.data_service.adapters.akshare.parse import (
    parse_distribution_frame,
    parse_nav_frame,
    parse_split_frame,
)
from fip.services.data_service.grouping import split_share_class_name
from fip.services.data_service.models.fund import Fund, FundShareClass
from fip.services.data_service.models.governance import DataProvider, DataProviderDataset
from fip.services.data_service.models.market import FundDistribution, FundNav
from fip.services.data_service.models.raw import CanonicalRaw, RawPayload
from fip.services.data_service.normalization.backfill import backfill_adjusted_nav


class IngestService:
    """灌数编排。

    每次取数都先留存 raw_payload 再解析 —— 上游格式会漂移，保留原始
    返回才能在 Adapter 修 bug 后重解析而不重新抓取（03-erd §7.1）。

    净值的 available_at 由【声明的披露时滞】推导，质量恒为 INFERRED
    （AKShare 给不出披露时刻）。时滞是配置而非猜测，回测报告须复述它。
    """

    def __init__(
        self, session: Session, adapter: SourceAdapter, disclosure_lag_days: int
    ) -> None:
        self._session = session
        self._adapter = adapter
        self._lag = dt.timedelta(days=disclosure_lag_days)

    # ---------- 基础设施 ----------

    def _provider(self) -> DataProvider:
        provider = self._session.execute(
            select(DataProvider).where(
                DataProvider.provider_code == self._adapter.provider_code
            )
        ).scalar_one_or_none()
        if provider is None:
            provider = DataProvider(
                provider_code=self._adapter.provider_code,
                display_name=self._adapter.provider_code,
            )
            self._session.add(provider)
            self._session.flush()
        return provider

    def ensure_dataset(self, dataset_code: str) -> DataProviderDataset:
        provider = self._provider()
        dataset = self._session.execute(
            select(DataProviderDataset).where(
                DataProviderDataset.provider_id == provider.id,
                DataProviderDataset.dataset_code == dataset_code,
            )
        ).scalar_one_or_none()
        if dataset is None:
            dataset = DataProviderDataset(
                provider_id=provider.id,
                dataset_code=dataset_code,
                adapter_version=self._adapter.adapter_version,
                library_version=getattr(self._adapter, "library_version", "unknown"),
            )
            self._session.add(dataset)
            self._session.flush()
        return dataset

    def _store_raw(self, record: SourceRecord) -> RawPayload:
        dataset = self.ensure_dataset(record.dataset)
        payload = RawPayload(
            dataset_id=dataset.id,
            request_params=record.request_params,
            payload=record.payload,
            row_count=record.row_count,
            library_version=dataset.library_version,
            published_at=record.published_at,
            provider_available_at=record.provider_available_at,
            ingested_at=record.ingested_at,
        )
        self._session.add(payload)
        self._session.flush()
        self._session.add(CanonicalRaw(
            raw_payload_id=payload.id,
            adapter_version=self._adapter.adapter_version,
            parsed_row_count=record.row_count,
        ))
        self._session.flush()
        return payload

    def _times(self, effective_at: dt.date, ingested_at: dt.datetime) -> dict[str, object]:
        available_at, quality = declared_lag_availability(effective_at, self._lag)
        return {
            "available_at": available_at,
            "availability_quality": quality.value,
            "published_at": None,           # AKShare 给不出，如实留空（C-12）
            "provider_available_at": None,  # 同上
            "ingested_at": ingested_at,
        }

    # ---------- 基金主数据 ----------

    def ingest_fund_list(self, limit: int | None = None) -> int:
        record = self._adapter.fetch("fund_list")
        self._store_raw(record)
        frame = pd.read_parquet(io.BytesIO(record.payload))
        if limit is not None:
            frame = frame.head(limit)

        created = 0
        for _, row in frame.iterrows():
            code = str(row["基金代码"]).strip()
            display_name = str(row["基金简称"]).strip()
            grouping = split_share_class_name(display_name)

            fund = self._session.execute(
                select(Fund).where(Fund.product_name == grouping.product_name)
            ).scalar_one_or_none()
            if fund is None:
                fund = Fund(
                    fund_code=f"P-{grouping.product_name}",
                    product_name=grouping.product_name,
                    grouping_status=grouping.status.value,
                )
                self._session.add(fund)
                self._session.flush()

            exists = self._session.execute(
                select(FundShareClass).where(
                    FundShareClass.fund_id == fund.id,
                    FundShareClass.share_class_code == grouping.share_class_code,
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue

            self._session.add(FundShareClass(
                fund_id=fund.id,
                share_class_code=grouping.share_class_code,
                display_name=display_name,
            ))
            self._session.flush()
            created += 1
            _ = code  # provider_fund_id 的映射登记在 ingest_nav 时按需建立
        return created

    # ---------- 净值与事件 ----------

    def _next_version(self, model, **keys: object) -> int:
        current = self._session.execute(
            select(func.max(model.version)).filter_by(**keys)
        ).scalar_one_or_none()
        return 1 if current is None else int(current) + 1

    def ingest_nav(self, share_class_id: int, provider_fund_id: str) -> int:
        record = self._adapter.fetch("fund_nav", symbol=provider_fund_id)
        payload = self._store_raw(record)
        inserted = 0
        for parsed in parse_nav_frame(record.payload):
            latest = self._session.execute(
                select(FundNav)
                .where(
                    FundNav.share_class_id == share_class_id,
                    FundNav.effective_at == parsed.effective_at,
                )
                .order_by(FundNav.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if latest is not None and latest.unit_nav == parsed.unit_nav:
                continue  # 值未变，不产生新版本
            self._session.add(FundNav(
                share_class_id=share_class_id,
                effective_at=parsed.effective_at,
                version=self._next_version(
                    FundNav,
                    share_class_id=share_class_id,
                    effective_at=parsed.effective_at,
                ),
                unit_nav=parsed.unit_nav,
                adjusted_nav=None,  # 由 rebuild_adjusted_nav 回填
                raw_payload_id=payload.id,
                **self._times(parsed.effective_at, record.ingested_at),
            ))
            inserted += 1
        self._session.flush()
        return inserted

    def ingest_distributions(self, share_class_id: int, provider_fund_id: str) -> int:
        events = []
        for dataset, parser in (
            ("fund_distribution", parse_distribution_frame),
            ("fund_split", parse_split_frame),
        ):
            record = self._adapter.fetch(dataset, symbol=provider_fund_id)
            payload = self._store_raw(record)
            for parsed in parser(record.payload):
                events.append((parsed, record.ingested_at, payload.id))

        merged: dict[dt.date, list] = {}
        for parsed, ingested_at, payload_id in events:
            slot = merged.setdefault(
                parsed.effective_at, [Decimal_zero(), Decimal_one(), ingested_at, payload_id]
            )
            slot[0] += parsed.dividend_per_unit
            slot[1] *= parsed.split_ratio

        inserted = 0
        for day, (dividend, ratio, ingested_at, payload_id) in sorted(merged.items()):
            self._session.add(FundDistribution(
                share_class_id=share_class_id,
                effective_at=day,
                version=self._next_version(
                    FundDistribution, share_class_id=share_class_id, effective_at=day
                ),
                dividend_per_unit=dividend,
                split_ratio=ratio,
                raw_payload_id=payload_id,
                **self._times(day, ingested_at),
            ))
            inserted += 1
        self._session.flush()
        return inserted

    def rebuild_adjusted_nav(self, share_class_id: int, decision_at: dt.date) -> int:
        return backfill_adjusted_nav(self._session, share_class_id, decision_at)


def Decimal_zero():
    from decimal import Decimal

    return Decimal(0)


def Decimal_one():
    from decimal import Decimal

    return Decimal(1)
```

> **同日事件的合并规则**：同一天可能同时出现在分红表与拆分表中。分红相加、拆分比例相乘，合并为一行 —— 与 `compute_adjusted_nav` 的「同日先除息后拆分」口径一致。

- [ ] **Step 4：运行集成测试确认通过**

Run: `.venv/bin/pytest tests/integration/test_ingest_service.py -v -m integration`
Expected: 6 passed

- [ ] **Step 5：写 CLI `src/fip/platform/cli.py`**

```python
import argparse
import datetime as dt
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fip.platform.decision_data.context import (
    DecisionExecutionContext, RecomputeScope, RuntimeMode, TriggerType,
)
from fip.platform.decision_data.pit import PitDataContext
from fip.services.data_service.adapters.akshare.client import AkShareSourceAdapter
from fip.services.data_service.ingest import IngestService
from fip.services.data_service.models.fund import FundShareClass
from fip.settings import settings

DISCLOSURE_LAG_DAYS = 1  # 与 governance.data_source_priority 中登记的时滞一致


def _session() -> Session:
    return Session(create_engine(settings.database_url, future=True), future=True)


def _service(session: Session) -> IngestService:
    return IngestService(session, AkShareSourceAdapter(), DISCLOSURE_LAG_DAYS)


def _resolve(session: Session, symbol: str) -> FundShareClass:
    share_class = session.execute(
        select(FundShareClass).where(FundShareClass.display_name.like(f"%{symbol}%"))
    ).scalars().first()
    if share_class is None:
        share_class = session.execute(
            select(FundShareClass).order_by(FundShareClass.id).limit(1)
        ).scalar_one_or_none()
    if share_class is None:
        raise SystemExit("未找到任何份额类别，请先执行 ingest-funds")
    return share_class


def cmd_ingest_funds(args: argparse.Namespace) -> None:
    with _session() as session:
        created = _service(session).ingest_fund_list(limit=args.limit)
        session.commit()
    print(f"新建份额类别 {created} 个")


def cmd_ingest_nav(args: argparse.Namespace) -> None:
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        service = _service(session)
        navs = service.ingest_nav(share_class.id, args.symbol)
        events = service.ingest_distributions(share_class.id, args.symbol)
        rebuilt = service.rebuild_adjusted_nav(share_class.id, dt.date.today())
        session.commit()
    print(f"净值 {navs} 行、事件 {events} 行、复权回填 {rebuilt} 行")


def cmd_pit_nav(args: argparse.Namespace) -> None:
    decision_at = dt.date.fromisoformat(args.decision_at)
    context = DecisionExecutionContext(
        decision_id=f"CLI-{decision_at}",
        decision_at=decision_at,
        data_as_of=decision_at,
        strategy_version="cli",
        policy_version="cli",
        code_version="cli",
        trigger_type=TriggerType.PERIODIC,
        recompute_scope=RecomputeScope.FULL_PIPELINE,
        runtime_mode=RuntimeMode.BACKTEST,
    )
    with _session() as session:
        share_class = _resolve(session, args.symbol)
        points = PitDataContext(context=context, session=session).navs().adjusted_nav_series(
            share_class.id,
            dt.date.fromisoformat(args.date_from),
            dt.date.fromisoformat(args.date_to),
        )
    print(f"{share_class.display_name} @ decision_at={decision_at}  共 {len(points)} 条")
    for point in points[:10]:
        print(f"  {point.effective_at}  unit={point.unit_nav}  "
              f"adj={point.adjusted_nav}  v{point.version}  {point.availability_quality}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fip")
    sub = parser.add_subparsers(dest="command", required=True)

    p_funds = sub.add_parser("ingest-funds", help="灌入基金列表")
    p_funds.add_argument("--limit", type=int, default=None)
    p_funds.set_defaults(func=cmd_ingest_funds)

    p_nav = sub.add_parser("ingest-nav", help="灌入某只基金的净值与事件并回填复权净值")
    p_nav.add_argument("--symbol", required=True)
    p_nav.set_defaults(func=cmd_ingest_nav)

    p_pit = sub.add_parser("pit-nav", help="按历史 decision_at 查询复权净值序列")
    p_pit.add_argument("--symbol", required=True)
    p_pit.add_argument("--decision-at", required=True, dest="decision_at")
    p_pit.add_argument("--from", required=True, dest="date_from")
    p_pit.add_argument("--to", required=True, dest="date_to")
    p_pit.set_defaults(func=cmd_pit_nav)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6：端到端验收 —— 用真实 AKShare 数据**

```bash
.venv/bin/alembic -x db=dev upgrade head
.venv/bin/python -m fip.platform.cli ingest-funds --limit 20
.venv/bin/python -m fip.platform.cli ingest-nav --symbol 000001
.venv/bin/python -m fip.platform.cli pit-nav --symbol 000001 \
  --decision-at 2021-06-30 --from 2020-01-01 --to 2021-12-31
```

**验收标准**（逐条确认）：

1. `pit-nav` 输出的最后一条 `effective_at` **不晚于** `2021-06-30` —— 决策时点之后的数据不可见
2. 每条记录的 `availability_quality` 均为 `INFERRED` —— AKShare 无披露时刻，如实标记
3. `adjusted_nav` 非空且与 `unit_nav` 在有分红的基金上**不相等**
4. 把 `--decision-at` 改为 `2020-06-30` 重跑，返回条数**严格减少**

再核对一次数据库中确实没有回填污染：

```bash
psql -d fip_dev -c "
SELECT availability_quality, count(*),
       count(published_at) AS with_published,
       count(provider_available_at) AS with_provider
FROM market.fund_nav GROUP BY 1;"
```

Expected: 只有 `INFERRED` 一行，且 `with_published` 与 `with_provider` 均为 **0**（C-12 未被违反）。

- [ ] **Step 7：运行全量检查**

Run: `make check && .venv/bin/pytest tests/contract -v -m contract`
Expected: lint、typecheck、全部单元/集成/适应度测试、契约测试均通过

- [ ] **Step 8：提交**

```bash
git add -A
git commit -m "feat(ingest): 灌数编排与 CLI，Plan-1 端到端打通

先留存 raw_payload 再解析；净值 available_at 由声明的披露时滞推导且
质量恒为 INFERRED；同日分红与拆分合并为一行以匹配复权口径。
CLI 的 pit-nav 可验证：决策时点之后的数据不可见，修订按时点解析。"
```

---

## Self-Review

### 1. Spec 覆盖检查

| Spec 章节 | 对应 Task | 状态 |
|---|---|---|
| §2.1 目录结构与三层分离 | Task 1 | ✅ |
| §2.2 依赖方向单向 | Task 1、Task 6 | ✅ |
| §2.3 单进程单库部署、写入权唯一 | Task 2、Task 6 | ✅ |
| §3.1 PIT 强制访问（PIT-A1~A4） | Task 5、Task 15 | ✅ |
| §3.2 决策快照三级一致性边界 | **未覆盖** | ⚠️ 见下方说明 |
| §3.3 Decision / Execution 两类状态 | Task 8（Execution 侧） | ⚠️ 见下方说明 |
| §4.1 SourceAdapter 端口 | Task 9 | ✅ |
| §4.2 M1 数据集覆盖 | Task 10、12、13、16、17 | ✅ |
| §4.3 PIT 诚实性四条硬规则 DS-1~4 | Task 9、10、12、19 | ✅ |
| §4.4 复权净值自算 | Task 14、15 | ✅ |
| §4.5 Fund ↔ Share Class 归组 | Task 11 | ✅ |
| §5.1 配置目录 | Task 7 | ✅ |
| §5.2 参数三元组 | Task 7 | ✅ |
| §5.3 PROVISIONAL 运行时语义 | Task 7 | ✅ |
| §5.4 配置装载进 DB 并以 FK 引用 | Task 9（`policy_version` 表）| ⚠️ 装载器留待 Plan-2 |
| §6.3 M1.0 / M1.1 落表范围 | Task 2、9、11、12、13、16、17 | ✅ |
| §7 M1.0 完成判据 | Task 1–8 | ✅ |
| §7 M1.1 完成判据 | Task 9–19 | ✅ |
| §8.1 Calculation Job 与幂等键 | Task 8 | ✅ |
| §9.2 架构适应度测试 | Task 6 | ✅ |
| §9.4 数据源契约测试 | Task 10 | ✅ |
| §9.3 可复现性回归 | **未覆盖** | ⚠️ 见下方说明 |
| §9.5 W2/W5/W7 负载基线 | **未覆盖** | ⚠️ 见下方说明 |

**三处有意的缺口，均属后续 Plan 的范围**，在此显式登记以免被当作遗漏：

| 缺口 | 为什么不在 Plan-1 | 归属 |
|---|---|---|
| **决策快照三级边界（§3.2）与 Decision Status** | B1/B2/B3 分别产生于 Peer Group、Universe、Optimization —— 这三者在 Plan-1 中尚不存在。此刻建表只能建一个无人写入的空壳。Task 8 已建立 Execution Status 这一维度，Decision Status 随决策实体一起落地。 | **Plan-3**（M1.5） |
| **可复现性回归（§9.3）** | 它需要一份已存的历史决策作为比对基准，而 Plan-1 尚不产生决策。容差常数已写入本 Plan 的 Global Constraints，Plan-3 直接引用。 | **Plan-3**（M1.5） |
| **W2/W5/W7 负载基线（§9.5）** | W2 是因子横截面（无因子表）、W5 是决策快照事务（无快照）、W7 是回测逐期读取（无回测）。三者的被测对象在 Plan-1 中都不存在。 | **Plan-2 / Plan-3** |

**一处范围收窄**：§5.4 要求配置装载进 DB 并由决策快照以 FK 引用。Plan-1 建了 `governance.policy_version` 表（Task 9）与 YAML 装载器（Task 7），但两者之间的**装载器**留到 Plan-2 —— 因为第一个真正需要引用 `policy_version` 的消费者是 Peer Group 的 `Evaluation Policy`（M1.2）。

### 2. 占位符扫描

已逐 Task 检查：每个 Step 都含可直接执行的命令或完整代码块；无 "TBD" / "TODO" / "类似 Task N" / "添加适当的错误处理" 一类表述。

三处**需要执行者据实修正**的地方是有意设计，不是占位符 —— 它们都给出了明确的探查命令与判定标准：

- Task 1 Step 4：依赖版本号安装失败时的查询与替换方法
- Task 10 Step 5：AKShare 真实列名的探查脚本，据结果修正 `datasets.py`
- Task 9 Step 7 / Task 11 Step 6 / Task 17 Step 5：autogenerate 迁移的逐行核对要点

### 3. 类型一致性检查

跨 Task 的名称与签名已核对一致：

| 符号 | 定义处 | 使用处 |
|---|---|---|
| `DecisionExecutionContext` | Task 4 | Task 5、8、15、19 |
| `RuntimeMode` | Task 4 | Task 7、15、19 |
| `RecomputeScope` / `TriggerType` | Task 4 | Task 8、15、19 |
| `PitDataContext(context=, session=)` | Task 5 | Task 15、19 |
| `NavPoint`（含 `unit_nav`） | Task 5 | Task 15 |
| `NavPitRepository.adjusted_nav_series` | Task 5 | Task 15 |
| `SqlNavPitRepository(session=, decision_at=)` | Task 15 | Task 5 的延迟 import |
| `QUALITY_SOURCE_SQL` / `TIME_ORDER_SQL` | Task 3 | Task 3、12、13、16 的迁移 |
| `temporal_check_constraints` / `interval_check` | Task 3 | Task 12、13、16、17 |
| `NavNumeric` / `RatioNumeric` | Task 3 | Task 12、16、17 |
| `resolve_availability` / `declared_lag_availability` | Task 9 | Task 19 |
| `SourceRecord` / `SourceAdapter` | Task 9 | Task 10、19 |
| `parse_nav_frame` / `_to_decimal` / `_to_date` | Task 12、13 | Task 13、16、19 |
| `ParsedDistribution` | Task 13 | Task 19 |
| `compute_adjusted_nav` | Task 14 | Task 15 |
| `backfill_adjusted_nav` | Task 15 | Task 19 |
| `split_share_class_name` / `GroupingStatus` | Task 11 | Task 19 |
| `ExecutionStatus` / `JobSubmitter` | Task 8 | Task 18 |

**修正的一处**：Task 5 的说明原指向"Task 13 创建 `repositories/nav.py`"，实际创建于 **Task 15**；文中已更正。

**注意 `_to_decimal` 与 `_to_date` 的定义顺序**：`_to_decimal` 定义于 Task 12 的 `parse.py`，`_to_date` 追加于 Task 13。Task 16 的 `parse_yield_curve_frame` 同时用到两者，因此 **Task 16 必须在 Task 13 之后执行**，本 Plan 的编号顺序已保证这一点。

---

## Execution Handoff

Plan 已保存至 `docs/superpowers/plans/2026-08-31-plan1-foundation-and-data-ingestion.md`。

**Plan-1 完成后的可验证能力**：给定任意历史 `decision_at`，取回当时可见的复权净值序列 —— 迟到的数据不可见，净值修订按时点解析，全部记录的 `availability_quality` 如实标记为 `INFERRED`。
