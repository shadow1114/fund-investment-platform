import datetime as dt
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
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


class FundEvaluation(Base):
    __tablename__ = "fund_evaluation"
    __table_args__ = (
        UniqueConstraint(
            "decision_id", "peer_group_snapshot_id", name="uq_fund_evaluation_decision_group"
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    peer_group_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.peer_group_snapshot.id", ondelete="RESTRICT"), nullable=False
    )
    factor_run_id: Mapped[int] = mapped_column(
        ForeignKey("factor.factor_run.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundScore(Base):
    __tablename__ = "fund_score"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_score_evaluation_share_class"
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    value: Mapped[float | None] = mapped_column(Numeric(24, 16))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64))


class FundScoreAttribution(Base):
    __tablename__ = "fund_score_attribution"
    __table_args__ = (
        UniqueConstraint("fund_score_id", "metric_id", name="uq_fund_score_attribution_metric"),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_score_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_score.id", ondelete="CASCADE"), nullable=False
    )
    metric_id: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FundRanking(Base):
    __tablename__ = "fund_ranking"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_ranking_evaluation_share_class"
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    rank: Mapped[float | None] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class FundTier(Base):
    __tablename__ = "fund_tier"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id", "share_class_id", name="uq_fund_tier_evaluation_share_class"
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"), nullable=False
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    tier: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class FundUniverseSnapshot(Base):
    __tablename__ = "fund_universe_snapshot"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_fund_universe_snapshot_decision"),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_evaluation.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version_id: Mapped[int] = mapped_column(
        ForeignKey("governance.policy_version.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FundUniverseMember(Base):
    __tablename__ = "fund_universe_member"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "share_class_id", name="uq_fund_universe_member"),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_universe_snapshot.id", ondelete="CASCADE"), nullable=False
    )
    share_class_id: Mapped[int] = mapped_column(
        ForeignKey("fund.fund_share_class.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class SelectionConditionRecord(Base):
    __tablename__ = "selection_condition_result"
    __table_args__ = (
        UniqueConstraint(
            "universe_member_id", "condition_id", name="uq_selection_condition_member_condition"
        ),
        {"schema": "evaluation"},
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    universe_member_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation.fund_universe_member.id", ondelete="CASCADE"), nullable=False
    )
    condition_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    passed: Mapped[bool | None] = mapped_column()
