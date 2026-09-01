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
    if not isinstance(node, dict):
        raise ValueError(f"配置节点 {prefix!r} 不是映射，无法解析")
    if _LEAF_KEYS & set(node):
        if "value" not in node:
            raise ValueError(f"配置叶子 {prefix!r} 缺少 value")
        if "status" not in node:
            raise ValueError(
                f"配置叶子 {prefix!r} 缺少 status —— "
                "无法区分已定案取值与开发期占位"
            )
        if "source" not in node:
            raise ValueError(f"配置叶子 {prefix!r} 缺少 source")
        out[prefix] = Parameter(
            path=prefix,
            value=node["value"],
            status=ParameterStatus(node["status"]),
            source=node["source"],
        )
        return
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
