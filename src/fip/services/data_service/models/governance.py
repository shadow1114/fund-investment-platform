import datetime as dt
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
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
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "dataset_code",
            name="uq_data_provider_dataset_code",
        ),
        {"schema": "governance"},
    )

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
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "field_name",
            "rule_version",
            name="uq_data_source_priority_rule",
        ),
        {"schema": "governance"},
    )

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
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
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
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
