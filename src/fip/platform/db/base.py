from sqlalchemy.orm import DeclarativeBase

SCHEMAS: tuple[str, ...] = (
    "raw",
    "fund",
    "market",
    "factor",
    "evaluation",
    "portfolio",
    "backtest",
    "governance",
)


class Base(DeclarativeBase):
    """全部 ORM 模型的基类。每个模型必须在 __table_args__ 中显式声明 schema。"""
