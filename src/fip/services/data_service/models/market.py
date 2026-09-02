import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.mixins import VersionedMixin, temporal_check_constraints
from fip.platform.db.types import NavNumeric, RatioNumeric


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
    # adjusted_nav 是【运维物化值，不是 PIT 真值来源】。
    #
    # 「正确的复权净值」是 (行, decision_at) 的【二元函数】：同一净值行在不同
    # 决策时点应有不同的复权值，因为它之后可能又披露了迟到的分红/拆分事件。
    # 一个每行一个标量的列装不下这个二元函数 —— 无论选哪个时刻盖章都是错的：
    # 盖「最后一个 checkpoint」会让迟到事件回头改写已可见的旧值（前视偏差），
    # 盖「首个 checkpoint」则让同一次查询里早期点不含该事件、晚期点含（口径
    # 不一致，在披露日附近伪造出一个收益尖峰）。见 Task 15 fix round 2 / 3。
    #
    # 因此 PIT 真值由 SqlNavPitRepository.adjusted_nav_series 按 decision_at
    # 【现算】。本列仍由 backfill_adjusted_nav 写入，用途仅限排查与快速目视
    # 核对，任何决策链路都不得读它。列保留、不改 schema。
    adjusted_nav: Mapped[Decimal | None] = mapped_column(NavNumeric, nullable=True)
    raw_payload_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class FundDistribution(Base, VersionedMixin):
    """除息与拆分事件。复权净值计算的唯一事件来源。

    dividend 与 split 合并为一张表：同日同时发生除息与拆分是真实场景，
    分两张表会让「同日先后顺序」这一关键语义无处安放。
    """

    __tablename__ = "fund_distribution"
    __table_args__ = (
        *temporal_check_constraints("fund_distribution"),
        # 同 fund_nav：值域约束必须与迁移保持一致，否则 autogenerate 会想删掉它们。
        CheckConstraint("dividend_per_unit >= 0", name="ck_fund_distribution_dividend"),
        CheckConstraint("split_ratio > 0", name="ck_fund_distribution_split"),
        # 同 fund_nav 的 ix_fund_nav_pit：迁移 0010 里建了这个索引，此处必须
        # 逐列声明（含 version DESC），否则 Base.metadata 看不到它，
        # autogenerate 会把数据库里已存在的索引当成待删除对象。
        Index(
            "ix_fund_distribution_pit",
            "share_class_id",
            "effective_at",
            "available_at",
            text("version DESC"),
        ),
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
        # 同 fund_nav / fund_distribution：PIT 版本解析的支撑索引必须与
        # 迁移 0011 里的 CREATE INDEX 逐列一致（含 version DESC），否则
        # Base.metadata 看不到它，autogenerate 会把它当成待删除对象。
        Index(
            "ix_risk_free_rate_pit",
            "currency",
            "tenor",
            "effective_at",
            "available_at",
            text("version DESC"),
        ),
        {"schema": "market"},
    )

    curve_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    currency: Mapped[str] = mapped_column(String(8), primary_key=True)
    tenor: Mapped[str] = mapped_column(String(8), primary_key=True)
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    rate: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)
    raw_payload_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
