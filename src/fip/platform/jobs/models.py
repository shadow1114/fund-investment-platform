import datetime as dt
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
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
    __table_args__ = (
        # 与迁移 0005 里的 CREATE INDEX 对齐 —— 只写进迁移会让 Base.metadata
        # 不知道它，后续 autogenerate 会把它当作待删除对象。
        Index("ix_calculation_job_status", "status"),
        {"schema": "governance"},
    )

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
