import logging
import pathlib
from collections.abc import Callable
from typing import Any

import yaml

from fip.platform.config.models import Parameter, ParameterStatus
from fip.platform.decision_data.context import RuntimeMode

logger = logging.getLogger(__name__)

_LEAF_KEYS = {"value", "status", "source"}


def _default_on_provisional_use(param: Parameter) -> None:
    logger.warning(
        "ProvisionalParameterUsed",
        extra={
            "event": "ProvisionalParameterUsed",
            "parameter_path": param.path,
            "parameter_source": param.source,
        },
    )


def _flatten(node: Any, prefix: str, out: dict[str, Parameter]) -> None:
    """将嵌套配置树展开为 dotted-path -> Parameter 的映射。

    叶子的判定要求【精确匹配】 {value, status, source} 三个字段，不多不少
    （见 spec §5.3 不阻断/不静默）：
      - 若字段集合与三键集合不相等，但仍有重叠（缺一两项，或夹带额外字段），
        说明作者想表达的既不是合法叶子也不是合法配置节，必须显式报错，
        而不是把多出来的/缺失的字段悄悄丢弃或强行凑成一个叶子。
      - 若字段集合恰好等于三键集合，但 value 本身又是一个映射，则该节点
        『长得像』叶子又『长得像』嵌套配置节，属于结构性歧义，同样必须
        报错，绝不能悄悄把嵌套结构塌陷成一个不透明的 value（那正是本模块
        存在的原因：绝不能让占位/未决结构被静默丢弃）。
      - value 为 null 同样拒绝：空值无法区分『已定案为空』与『遗漏未填』。
    """
    if not isinstance(node, dict):
        raise ValueError(f"配置节点 {prefix!r} 不是映射，无法解析")

    keys = set(node)
    overlap = _LEAF_KEYS & keys

    if keys == _LEAF_KEYS:
        if isinstance(node["value"], dict):
            raise ValueError(
                f"配置节点 {prefix!r} 恰好含有 value/status/source 三个字段，"
                "但 value 本身又是一个映射 —— 无法判断这是一个标量参数叶子，"
                "还是一个被同名字段掩盖的嵌套配置节，请调整字段名或结构"
            )
        if node["value"] is None:
            raise ValueError(
                f"配置叶子 {prefix!r} 的 value 为空(null) —— "
                "空值无法区分『已定案为空』与『遗漏未填』"
            )
        out[prefix] = Parameter(
            path=prefix,
            value=node["value"],
            status=ParameterStatus(node["status"]),
            source=node["source"],
        )
        return

    if overlap:
        missing = sorted(_LEAF_KEYS - keys)
        extra = sorted(keys - _LEAF_KEYS)
        detail = []
        if missing:
            detail.append(f"缺少 {missing}")
        if extra:
            detail.append(f"另有非叶子字段 {extra}")
        raise ValueError(
            f"配置节点 {prefix!r} 含有部分叶子字段 {sorted(overlap)}，"
            f"{'，'.join(detail)} —— 既不是合法的参数叶子，也不是合法的配置节"
        )

    for key, child in node.items():
        _flatten(child, f"{prefix}.{key}" if prefix else str(key), out)


class ConfigSet:
    """一组已装载的参数。

    PROVISIONAL 参数的运行时语义（spec §5.3）：
      BACKTEST —— 允许使用，记录使用清单（落入回测报告的配置章节）
      LIVE     —— 允许使用，记录清单【并】发出告警事件
    两种模式下都【不阻断】：阻断会让链路无法端到端运行；
    但都【不静默】：静默会让占位值伪装成已定案值。
    """

    def __init__(
        self,
        parameters: dict[str, Parameter],
        runtime_mode: RuntimeMode,
        on_provisional_use: Callable[[Parameter], None] | None = None,
    ) -> None:
        self._parameters = parameters
        self._runtime_mode = runtime_mode
        self._on_provisional_use = on_provisional_use or _default_on_provisional_use
        self._provisional_used: set[str] = set()

    def get(self, path: str) -> Any:
        try:
            param = self._parameters[path]
        except KeyError:
            raise KeyError(f"配置项不存在：{path}") from None
        if param.status is ParameterStatus.PROVISIONAL:
            self._provisional_used.add(param.path)
            if self._runtime_mode is RuntimeMode.LIVE:
                self._on_provisional_use(param)
        return param.value

    @property
    def provisional_parameters_used(self) -> tuple[str, ...]:
        """本次执行消费到的 PROVISIONAL 参数清单，写入决策快照。"""
        return tuple(sorted(self._provisional_used))

    @property
    def parameters(self) -> dict[str, Parameter]:
        return dict(self._parameters)


def load_config_file(
    path: pathlib.Path,
    runtime_mode: RuntimeMode,
    on_provisional_use: Callable[[Parameter], None] | None = None,
) -> ConfigSet:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    flat: dict[str, Parameter] = {}
    _flatten(raw, "", flat)
    return ConfigSet(flat, runtime_mode, on_provisional_use)
