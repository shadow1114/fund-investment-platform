from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from fip.platform.db.autogenerate import include_object
from fip.platform.db.base import Base

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
from fip.services.data_service.models import (
    benchmark,  # noqa: F401 — services 层
    fund,  # noqa: F401 — services 层
    governance,  # noqa: F401 — services 层
    market,  # noqa: F401 — services 层
    raw,  # noqa: F401 — services 层
)
from fip.settings import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# include_object 的排除清单住在 fip.platform.db.autogenerate ——
# env.py 在 Alembic 之外无法被 import（模块级就调 context.config），
# 而 G-16 的闸门测试 tests/integration/test_autogenerate_gate.py 必须
# 用【同一份】规则，不能复制。见该模块的 docstring。


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
