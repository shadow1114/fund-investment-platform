import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from fip.platform.db.base import Base
from fip.settings import settings

# 下面这组 import 是 Base.metadata 的唯一注册点：每新增一个定义了 ORM
# model（Base 子类）的模块，都必须在此追加一行 import，否则该模块不会被
# 加载、其表就不会出现在 Base.metadata 里，`alembic revision --autogenerate`
# 会静默地看不到它 —— 轻则生成的迁移漏建该表，重则误判它是要被 DROP 的对象。
# env.py 位于 src/fip 之外，不受 platform 层不得在模块级 import services 层
# 这条架构约束（tests/fitness/test_architecture.py）约束，因此可以在一处
# 同时收纳 platform 层与 services 层的 model 模块，不必像早前那样按层拆分成
# 两个注册文件。
# tests/fitness/test_architecture.py 里的
# test_every_orm_model_module_is_registered_in_env 会校验这份列表与
# src/fip 下实际存在的 Base 子类模块一致，防止本清单被遗忘。
from fip.platform.jobs import models as jobs_models  # noqa: F401 — platform 层
from fip.services.data_service.models import fund  # noqa: F401 — services 层
from fip.services.data_service.models import governance  # noqa: F401 — services 层
from fip.services.data_service.models import market  # noqa: F401 — services 层
from fip.services.data_service.models import raw  # noqa: F401 — services 层

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# autogenerate 需要一份显式、最小化的排除清单，而不是一条宽松的「忽略未建模
# 对象」规则 —— 宽松规则会连真实的 schema drift 也一并吞掉，这正是本清单
# 要防止的失效模式。清单里的每一项都必须能单独解释「为什么被排除」。
#
# 1) market.fund_nav_<年份> 分区子表：PostgreSQL 声明式分区下，
#    `CREATE TABLE ... PARTITION OF` 产生的物理子表是父表 DDL 的派生物，
#    SQLAlchemy 没有对应的 ORM 概念可以声明它们（parent table 本身已经
#    通过 FundNav 声明，子表继承其列与约束）。不排除的话，autogenerate
#    会把 31 张分区子表全部当成「Base.metadata 里没有、数据库里多出来」
#    的表，提议逐一 DROP —— 一旦真的被误执行，丢的是全部历史净值。
#    用命名模式而非表名枚举来匹配，因为分区范围会随 FIRST_YEAR/LAST_YEAR
#    调整（见 0008 迁移），排除规则不应该每次跟着改。
# 2) governance.mixin_probe / governance.interval_probe：0002 / 0004 迁移
#    引入的纯 SQL 约束测试夹具，按设计没有 ORM model（校验的是 mixin 生成的
#    CHECK 约束本身，不是业务表）。它们的存在性由 tests/fitness 里对应的
#    18 个约束测试覆盖，不依赖 autogenerate 能看见它们 —— 所以就算被真的
#    删除，autogenerate 保持沉默也不会丢失覆盖。这是本清单里唯一一类
#    「明知道 autogenerate 看不见其消失」的例外，写在这里防止将来有人
#    收紧排除规则（导致这两张表重新产生噪音）或不明就里地放宽排除规则
#    （导致这条注释失去意义、掩盖真实 drift）。
_PARTITION_CHILD_RE = re.compile(r"^fund_nav_\d{4}$")
_EXCLUDED_GOVERNANCE_TABLES = {"mixin_probe", "interval_probe"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and reflected and compare_to is None:
        if object.schema == "market" and _PARTITION_CHILD_RE.match(name or ""):
            return False
        if object.schema == "governance" and name in _EXCLUDED_GOVERNANCE_TABLES:
            return False
    return True


def _url() -> str:
    which = context.get_x_argument(as_dictionary=True).get("db", "dev")
    return settings.test_database_url if which == "test" else settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=include_object,
    )
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
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
