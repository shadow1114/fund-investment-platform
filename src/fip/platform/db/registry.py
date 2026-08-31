"""模型注册表 —— Alembic autogenerate 的元数据来源。

env.py 导入本模块，本模块导入全部 ORM model 模块，使它们注册到
Base.metadata 上。若不这样做，Base.metadata 在 autogenerate 时为空，
生成的迁移会 DROP 掉全部既有表。

【每新增一个 model 模块，必须在此追加一行 import。】
"""

# 尚无 model 模块。后续任务在此追加，例如：
# from fip.services.data_service.models import fund  # noqa: F401
