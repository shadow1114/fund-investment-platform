import datetime as dt

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


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


class ProviderFundIdentity(Base):
    """Provider 的基金 ID 映射。

    【不得】把 provider_fund_id 做成 Share Class 的列 —— 那会限制为单
    Provider，且映射变化会污染主数据（03-erd §5.3）。映射本身可能变化，
    因此带 valid_from / valid_to。
    """

    __tablename__ = "provider_fund_identity"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "provider_fund_id", "valid_from",
            name="uq_provider_identity",
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
    valid_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
