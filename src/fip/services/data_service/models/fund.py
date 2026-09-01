import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base
from fip.platform.db.mixins import (
    IntervalMixin,
    VersionedMixin,
    interval_check,
    interval_temporal_check_constraints,
    temporal_check_constraints,
)
from fip.platform.db.types import RatioNumeric


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


class ProviderFundIdentity(Base, IntervalMixin):
    """Provider 的基金 ID 映射 —— 【区间型表】（04-database-design §6.2）。

    【不得】把 provider_fund_id 做成 Share Class 的列 —— 那会限制为单
    Provider，且映射变化会污染主数据（03-erd §5.3）。映射本身可能变化，
    因此带 valid_from / valid_to；而 Provider 可能重新分配同一个
    (provider_id, provider_fund_id) 指向不同的 Share Class（§6.2.1），
    所以本表必须携带 IntervalMixin 的完整时序列 —— available_at 是判定
    「某个时点我们知道的映射是哪一条」的唯一依据，缺失它会让 PIT 查询
    静默退化为读今天的映射（前视偏差）。

    时序约束用 interval_temporal_check_constraints（不含 clause 1 / clause 4）
    而非版本化表的 temporal_check_constraints：Provider 重指派几乎总是提前
    公告，available_at / published_at 早于 valid_from 是常态，不是违规。

    uq_pfi_open_interval 是「同一 (provider, provider_fund_id) 至多一条开放
    区间」的【数据库不变式】。唯一键 uq_pfi_provider_key 带 valid_from，
    允许两条 valid_to IS NULL、valid_from 不同的行共存，此时 cli._resolve 的
    `ORDER BY valid_from DESC LIMIT 1` 会静默挑一条 —— 挑错就是把一只基金的
    净值写进另一只基金的 PIT 历史。应用层的 read-then-write 守卫不是数据库
    不变式：它拦不住并发，也拦不住任何绕开 IngestService 的写入路径。
    """

    __tablename__ = "provider_fund_identity"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "provider_fund_id", "valid_from",
            name="uq_pfi_provider_key",
        ),
        *interval_temporal_check_constraints("provider_fund_identity"),
        interval_check("provider_fund_identity"),
        Index("idx_pfi_share_class", "share_class_id"),
        # 部分唯一索引，须与迁移 0014 里的 CREATE UNIQUE INDEX 逐字一致
        # （含 WHERE 子句），否则 autogenerate 会把它当成待删除对象 ——
        # 本仓库已三次被「库里有约束而 ORM metadata 里没有」咬出误删迁移。
        Index(
            "uq_pfi_open_interval",
            "provider_id",
            "provider_fund_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
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
        *interval_temporal_check_constraints("fund_manager_assignment"),
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
        *interval_temporal_check_constraints("fund_classification_history"),
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
        *interval_temporal_check_constraints("fund_status_history"),
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
        *interval_temporal_check_constraints("fund_fee"),
        interval_check("fund_fee"),
        {"schema": "fund"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    fee_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rate: Mapped[Decimal] = mapped_column(RatioNumeric, nullable=False)


class InvestmentEligibility(Base, VersionedMixin):
    """可投资性 —— 派生实体，但派生规则本身会被修订（04-database-design §6.4.1）。

    不是 IntervalMixin：区间模型没有地方安放「同一份修订后的结论」——
    只能覆盖或用第二段区间部分遮盖第一段，两者都丢失了「当时相信的是
    什么」。version 记录的正是「这条结论出自哪一版派生规则」，因此本表
    与 fund_nav / fund_distribution / risk_free_rate 同属三时点 + version
    的事实型模式（03-erd §15.1 状态型清单未列出本实体），PK 为
    (share_class_id, effective_at, version)。因此用版本化表的
    temporal_check_constraints（四子句，anchor = effective_at），
    【不得】改用 interval_temporal_check_constraints —— 本表没有
    valid_from/valid_to，它的 effective_at 是「事实成立日」而非
    「区间起点」，clause 1 / clause 4 在这里仍然是真正的前视偏差防线。
    """

    __tablename__ = "investment_eligibility"
    __table_args__ = (
        *temporal_check_constraints("investment_eligibility"),
        # PIT 版本解析的支撑索引，须与迁移 0013 里的 CREATE INDEX 逐列一致
        # （含 version DESC），否则 autogenerate 会把它当成待删除对象。
        Index(
            "ix_investment_eligibility_pit",
            "share_class_id",
            "available_at",
            text("version DESC"),
        ),
        {"schema": "fund"},
    )

    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    effective_at: Mapped[dt.date] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    eligibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
