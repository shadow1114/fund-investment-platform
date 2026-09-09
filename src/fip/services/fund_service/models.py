import datetime as dt

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class PeerGroupSnapshot(Base):
    __tablename__ = "peer_group_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "classification_code",
            "base_currency",
            name="uq_peer_group_snapshot_decision_key",
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    classification_code: Mapped[str] = mapped_column(String(32), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"), nullable=False
    )
    decision_at: Mapped[dt.date] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)


class PeerGroupMember(Base):
    __tablename__ = "peer_group_member"
    __table_args__ = {"schema": "evaluation"}
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="CASCADE"), primary_key=True
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
