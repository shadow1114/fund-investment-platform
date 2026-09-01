import datetime as dt
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from fip.platform.db.base import Base


class RawPayload(Base):
    """Provider 的原始返回，序列化为 parquet。【不可修改】。

    保留它是 Adapter 修 bug 后可重解析的前提 —— 否则只能重新抓取，
    而上游的历史数据可能已经变了。
    """

    __tablename__ = "raw_payload"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("governance.data_provider_dataset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    library_version: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provider_available_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CanonicalRaw(Base):
    """一次 payload 的解析产物。同一 payload 可被多次重新解析（1:N）。"""

    __tablename__ = "canonical_raw"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    raw_payload_id: Mapped[int] = mapped_column(
        ForeignKey("raw.raw_payload.id", ondelete="RESTRICT"), nullable=False
    )
    adapter_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parsed_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
