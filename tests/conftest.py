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
        # 整体丢弃 public schema（而非逐个丢弃已知的枚举类型）：后续任务会在
        # public 中新增更多枚举（如 execution_status_enum），若只删业务 schema
        # 和当前已知枚举，第二次测试会话会因“type already exists”而失败。
        # 整体重建 public 一次性清空所有类型与 alembic_version，且无需随新枚举
        # 增加而维护。
        for schema in SCHEMAS:
            conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
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
