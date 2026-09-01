import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, text
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
        # 值域约束必须【同时】声明在 ORM 与迁移中。只写进迁移会让
        # Base.metadata 不知道它，后续 autogenerate 便会生成一条 DROP。
        CheckConstraint("unit_nav > 0", name="ck_fund_nav_positive"),
        # PIT 版本解析的支撑索引，必须与迁移 0008 里的 CREATE INDEX 逐列一致
        # （含 version DESC）—— 同样是为了让 Base.metadata 如实反映已存在的
        # schema，否则 autogenerate 会把它当作待删除对象。
        Index(
            "ix_fund_nav_pit",
            "share_class_id",
            "effective_at",
            "available_at",
            text("version DESC"),
        ),
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
