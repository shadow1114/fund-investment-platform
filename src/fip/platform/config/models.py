from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ParameterStatus(StrEnum):
    PROVISIONAL = "PROVISIONAL"  # 实现期占位，待投研定案
    DECIDED = "DECIDED"          # 已定案


@dataclass(frozen=True, slots=True)
class Parameter:
    """配置叶子的三元组。

    status 与 source 是必填的：只有 value 的参数无法区分
    『已定案的取值』与『开发期的占位』。
    """

    path: str
    value: Any
    status: ParameterStatus
    source: str
