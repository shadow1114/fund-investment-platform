"""模型注册表 —— Alembic autogenerate 的元数据来源（仅 platform 层模型）。

env.py 导入本模块，本模块导入 platform 层的全部 ORM model 模块，使它们
注册到 Base.metadata 上。若不这样做，Base.metadata 在 autogenerate 时为空，
生成的迁移会 DROP 掉全部既有表。

本模块只能收纳 platform 层的 model 模块：`tests/fitness/test_architecture.py`
的 `test_platform_layer_does_not_import_services_at_module_level` 禁止
platform 层在模块级 import services 层。services 层（如
`fip.services.data_service.models`）的 model 模块改由 env.py 直接 import
注册，不经过本文件。

【每新增一个 platform 层 model 模块，必须在此追加一行 import；
services 层的 model 模块请在 env.py 里追加。】
"""

from fip.platform.jobs import models as jobs_models  # noqa: F401
